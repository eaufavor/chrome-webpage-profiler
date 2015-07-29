#!/usr/bin/env python

import os, sys, logging, argparse, pprint, json, time
from chrome_loader import ChromeLoader
from firefox_loader import FirefoxLoader
from multiprocessing import Process, JoinableQueue
from loader import LoadResult
import traceback

GLOBAL_DEFAULT = {'headless': True, 'log_ssl_keys': False, 'disable_quic': True,
                  'disable_spdy': False, 'ignore_certificate_errors': False,
                  'browser': 'chrome', 'parallel': 1}
LOCAL_DEFAULT = {'num_trials': 1, 'save_har': True, 'save_packet_capture': False,
                 'save_screenshot': True, 'fresh_view': True}
PRIVATE_DEFAULT = {'har_file_name': None, 'packet_capture_file_name': None,
                   'screenshot_name': None, 'preload': []}

def prepare_tests_settings(tests):
    """ this fucntion load those parameters from default setting to each test
        if they are not present in the test before"""
    defaultSettings = tests['default']
    if not defaultSettings:
        tests['default'] = {}
    for k in LOCAL_DEFAULT:
        if k not in tests['default']:
            tests['default'][k] = LOCAL_DEFAULT[k]

    for i in range(len(tests['tests'])):
        test = tests['tests'][i]
        for k in defaultSettings:
            if k not in test:
                test[k] = defaultSettings[k]
        for k in PRIVATE_DEFAULT:
            if k not in test:
                test[k] = PRIVATE_DEFAULT[k]
        tests['tests'][i] = test

    for k in GLOBAL_DEFAULT:
        if k not in tests['default']:
            tests['default'][k] = GLOBAL_DEFAULT[k]

    return

def loader_worker(my_id, default, job_queue, result_queue):
    if default['browser'].lower() == 'chrome':
        loader = ChromeLoader(disable_quic=default['disable_quic'], disable_spdy=default['disable_spdy'],
                              check_protocol_availability=False, save_packet_capture=True,
                              log_ssl_keys=default['log_ssl_keys'], save_har=True, disable_local_cache=False,
                              headless=default['headless'], ignore_certificate_errors=default['ignore_certificate_errors'])
        if not loader.setup(my_id):
            logging.error('Error setting up loader')
            return
    else:
        # TODO: firefox
        return

    while True:
        testJob = job_queue.get()
        if testJob[1] < 0: # a reseved number to tell workers to quit
            loader.teardown()
            job_queue.task_done()
            return
        try:
            result = loader.load_page(testJob[0], testJob[1])
            if result:
                result_queue.put(result)
            if result.status == LoadResult.FAILURE_TIMEOUT:
                loader.teardown()
                if not loader.setup(my_id):
                    logging.error('Error setting up loader')
                    return
        except Exception as e:
            logging.exception('Error loading pages: %s\n%s', e, traceback.format_exc())
            loader.teardown()
            if not loader.setup(my_id):
                logging.error('Error setting up loader')
                return
        finally:
            # stop tcpdump (if it's running)
            try:
                if loader.tcpdump_proc:
                    logging.debug('Stopping tcpdump')
                    os.system("kill %s" % loader.tcpdump_proc.pid)
                    loader.tcpdump_proc = None
            except Exception:
                logging.exception('Error stopping tcpdump.')
            job_queue.task_done()


def check_alive(workers):
    for worker in workers:
        if worker.is_alive():
            return True
    return False
def daemon_process(workers, queue):
    while True:
        time.sleep(1)
        if not check_alive(workers):
            break
    #clean up
    while not queue.empty():
        _ = queue.get()
        queue.task_done()

def start_parallel_instances(default, job_queue, result_queue):
    workers = []
    for i in range(default['parallel']):
        worker = Process(name='loader_worker%d'%i, target=loader_worker, args=(i, default, job_queue, result_queue))
        workers.append(worker)

    for worker in workers:
        worker.daemon = True
        logging.info('Starting worker: %s', worker.name)
        worker.start()
    daemon = Process(name='daemon', target=loader_worker, args=(workers, job_queue))
    daemon.start()
    return workers

def dispatch_parallel_tests(tests, queue):
    for test in tests['tests']:
        for i in range(0, test['num_trials']):
            current_test = [test, i]
            queue.put(current_test)

def teardown_parallel_instances(default, job_queue):
    for _ in range(default['parallel']):
        job_queue.put([None, -1])
    time.sleep(0.5)

def main(fileName):

    with open(fileName, 'r') as f:
        tests = json.load(f)
    prepare_tests_settings(tests)
    default = tests['default']
    jobQueue = JoinableQueue()
    resultQueue = JoinableQueue()
    # NOTE: some parameters are obsolete as they are overruled by the settings in tests
    if default['browser'].lower() == 'chrome':
        start_parallel_instances(default, jobQueue, resultQueue)
        dispatch_parallel_tests(tests, jobQueue)
        #loader = ChromeLoader(disable_quic=default['disable_quic'], disable_spdy=default['disable_spdy'],
        #                      check_protocol_availability=False, save_packet_capture=True,
        #                      log_ssl_keys=default['log_ssl_keys'], save_har=True, disable_local_cache=False,
        #                      headless=default['headless'], ignore_certificate_errors=default['ignore_certificate_errors'])
        #loader.load_pages(tests)
        #pprint.pprint(dict(loader.load_results))
        jobQueue.join()
        while not resultQueue.empty():
            result = resultQueue.get(False)
            print result
            resultQueue.task_done()
        teardown_parallel_instances(default, jobQueue)
        jobQueue.join()
    elif default['browser'].lower() == 'firefox':
        loader = FirefoxLoader(disable_quic=default['disable_quic'], disable_spdy=default['disable_spdy'],
                               check_protocol_availability=False, save_packet_capture=True,
                               log_ssl_keys=default['log_ssl_keys'], save_har=True, disable_local_cache=False,
                               headless=default['headless'], ignore_certificate_errors=default['ignore_certificate_errors'])
        loader.load_pages(tests)
        pprint.pprint(dict(loader.load_results))
    else:
        logging.critical('Uknown browser %s', default['browser'].lower())
        sys.exit(-1)

    #pprint.pprint(dict(loader.page_results))

if __name__ == "__main__":
    # set up command line args
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                                     description='Web page profiler.')
    parser.add_argument('tests', help='A json file that describes the web page tests. See README.md for details')
    parser.add_argument('-o', '--outdir', default='.', help='Destination directory for HAR files.')
    parser.add_argument('-q', '--quiet', action='store_true', default=False, help='only print errors')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='print debug info. --quiet wins if both are present')
    args = parser.parse_args()

    if not os.path.isdir(args.outdir):
        try:
            os.makedirs(args.outdir)
        except Exception as _:
            logging.getLogger(__name__).error('Error making output directory: %s', args.outdir)
            sys.exit(-1)

    # set up logging
    if args.quiet:
        level = logging.WARNING
    elif args.verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(
        format = "%(levelname) -10s %(asctime)s %(module)s:%(lineno) -7s %(message)s",
        level = level
    )

    main(args.tests)
