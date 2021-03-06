import os
import subprocess
import logging
from time import sleep
from loader import Loader, LoadResult, Timeout, TimeoutError

CHROME = '/usr/bin/env google-chrome'
CHROME_HAR_CAPTURER = '/usr/bin/env chrome-har-capturer'
XVFB = '/usr/bin/env Xvfb'
#DISPLAY = ':%s'%os.geteuid()

# TODO: test if isntalled chrome can support HTTP2
# TODO: pick different display if multiple instances are used at once
# TODO: get load time
# TODO: screenshot?
# TODO: final URL?
# TODO: pass timeout to chrome?
# TODO: FAILURE_NO_200?
# TODO: Cache-Control header

class ChromeLoader(Loader):
    '''Subclass of :class:`Loader` that loads pages using Chrome.

    .. note:: The :class:`ChromeLoader` currently does not time page load.
    .. note:: The :class:`ChromeLoader` currently does not support single-object loading (i.e., it always loads the full page).
    .. note:: The :class:`ChromeLoader` currently does not support disabling network caches.
    '''

    def __init__(self, **kwargs):
        super(ChromeLoader, self).__init__(**kwargs)
        if not self._full_page:
            raise NotImplementedError('ChromeLoader does not support loading only an object')
        if self._disable_network_cache:
            raise NotImplementedError('ChromeLoader does not support disabling network caches.')

        self._xvfb_proc = None
        self._chrome_proc = None
        self.DISPLAY = None
        self.debug_port = None
        self._devnull = None

    def _preload_objects(self, preloads, fresh):
        logging.debug('preloading objects')

        # no need to save HAR
        harpath = '/dev/null'

        for url in preloads:
            logging.debug('preloading %s', url)
            try:
                # tell har capturer not to clean cache or connections
                preload_flag = '-n'

                if fresh:
                    # if do want to clean cache, do it once
                    preload_flag = ''
                    fresh = False

                # load objects as if there are pages
                # delay 10ms could be even smaller
                capturer_cmd = '%s -d 10 ' % CHROME_HAR_CAPTURER + preload_flag +\
                               ' -p %d '%(self.debug_port) + ' -o %s %s' % (harpath, url)

                logging.debug('Running capturer: %s', capturer_cmd)
                with Timeout(seconds=self._timeout+5):
                    subprocess.check_call(capturer_cmd.split(),\
                        stdout=self._stdout_file, stderr=subprocess.STDOUT)
            except TimeoutError:
                logging.exception('* Timeout fetching %s', url)
                return LoadResult(LoadResult.FAILURE_TIMEOUT, url)
            except subprocess.CalledProcessError as e:
                logging.exception('Error loading %s: %s\n%s', url, e, e.output)
                return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
            except Exception as e:
                logging.exception('Error loading %s: %s', url, e)
                return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
            logging.debug('Object loaded.')



    def _load_page(self, test, _, trial_num=-1):

        url = test['url']

        # path for new HAR file
        if test['save_har']:
            prefix = test['har_file_name'] if test['har_file_name'] else url
            harpath = self._outfile_path(prefix, suffix='.har', trial=trial_num)
        else:
            harpath = '/dev/null'
        logging.debug('Will save HAR to %s', harpath)

        # load the specified URL
        logging.info('Fetching page %s', url)

        try:
            repeat_flag = '-r'
            if test['fresh_view']:
                repeat_flag = ''
            # wait 0.5s between pages, could be smaller
            capturer_cmd = '%s -d 500 ' % CHROME_HAR_CAPTURER + repeat_flag +\
                           ' -p %d'%self.debug_port +\
                           ' -o %s %s' % (harpath, url)
            logging.debug('Running capturer: %s', capturer_cmd)
            with Timeout(seconds=self._timeout+5):
                subprocess.check_call(capturer_cmd.split(),\
                    stdout=self._stdout_file, stderr=subprocess.STDOUT)
        except TimeoutError:
            logging.exception('* Timeout fetching %s', url)
            return LoadResult(LoadResult.FAILURE_TIMEOUT, url)
        except subprocess.CalledProcessError as e:
            logging.exception('Error loading %s: %s\n%s', url, e, e.output)
            return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
        except Exception as e:
            logging.exception('Error loading %s: %s', url, e)
            return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
        logging.debug('Page loaded.')

        return LoadResult(LoadResult.SUCCESS, url, har=harpath)


    def _setup(self, my_id=0):
        stdout = self._stdout_file
        self._devnull = open(os.devnull, 'w')
        #stderr = self._stdout_file

        # assign a unique debug port for the current chrome
        # pid*10+my_id+1000
        # valid port number 1000~65536
        # NOTE: this simple formula does not guarantee conflict-free
        self.debug_port = (os.getuid()*10+my_id)%64536 + 1000
        if self._headless:
            # start a virtual display
            try:
                # try to get a unique display number of the virtual buffer
                self.DISPLAY = ":%s"%(os.geteuid()*10+my_id)
                os.environ['DISPLAY'] = self.DISPLAY
                xvfb_command = '%s %s -screen 0 1366x768x24 -ac' % (XVFB, self.DISPLAY)

                logging.debug('Starting XVFB: %s', xvfb_command)
                self._xvfb_proc = subprocess.Popen(xvfb_command.split(),\
                    stdout=stdout, stderr=self._devnull)
                sleep(0.5)

                # check if Xvfb failed to start and process terminated
                retcode = self._xvfb_proc.poll()
                if retcode != None:
                    raise Exception("Xvfb proc exited with return code: %d" % retcode)
            except Exception as _:
                logging.exception("Error starting XFVB")
                return False
            logging.debug('Started XVFB (DISPLAY=%s)', os.environ['DISPLAY'])

        if self._log_ssl_keys:
            # the browser appends new keys to this file without overwrite the old content
            keylog_file = os.path.join(self._outdir, 'ssl_keylog')
            os.environ['SSLKEYLOGFILE'] = keylog_file


        # launch chrome with no cache and remote debug on
        try:
            options = ''
            if self._user_agent:
                options += ' --user-agent="%s"' % self._user_agent
            if self._disable_local_cache:
                options += ' --disable-application-cache --disable-cache'
            if self._disable_quic:
                options += ' --disable-quic'
            if self._disable_spdy:
                options += ' --use-spdy=off'
            if self._ignore_certificate_errors:
                options += ' --ignore-certificate-errors'
            # options for chrome-har-capturer
            # options += ' about:blank --remote-debugging-port=9222 --enable-benchmarking --enable-net-benchmarking --disk-cache-dir=/tmp'
            # --user-data-dir allows multiple chromes to launch under the same user
            # first run could be slow as a lot new files needs to be set up
            # mount /tmp/tmpfs as ram based fs could speed things up
            options += ' about:blank --remote-debugging-port=%d --user-data-dir=/tmp/tmpfs/%d/ '\
                       '--enable-benchmarking --enable-net-benchmarking'%(self.debug_port, self.debug_port)

            chrome_command = '%s %s' % (CHROME, options)
            logging.debug('Starting Chrome: %s', chrome_command)
            self._chrome_proc = subprocess.Popen(chrome_command.split(),\
                stdout=stdout, stderr=self._devnull)
            sleep(2)

            # check if Xvfb failed to start and process terminated
            retcode = self._chrome_proc.poll()
            if retcode != None:
                raise Exception("Chrome proc exited with return code: %i" % retcode)
        except Exception as _:
            logging.exception("Error starting Chrome")
            return False
        logging.debug('Started Chrome')
        return True


    def _teardown(self):
        if self._chrome_proc:
            logging.debug('Stopping Chrome')
            self._chrome_proc.terminate()
            #self._chrome_proc.kill()
            self._chrome_proc.wait()

        # kill any subprocesses chrome might have opened
        #try:
        #    subprocess.check_output('killall chrome'.split(), stderr=self._devnull)
        #except Exception as e:
        #    logging.info('Cannot Kill all remaining chrome processes (maybe there were none): %s', e)

        if self._xvfb_proc:
            logging.debug('Stopping XVFB')
            self._xvfb_proc.terminate()
            self._xvfb_proc.wait()
        self._devnull.close()
