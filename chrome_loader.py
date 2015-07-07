import os
import subprocess
import logging
from time import sleep
from loader import Loader, LoadResult, Timeout, TimeoutError

CHROME = '/usr/bin/env google-chrome'
CHROME_HAR_CAPTURER = '/usr/bin/env chrome-har-capturer'
XVFB = '/usr/bin/env Xvfb'
DISPLAY = ':99'

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
    .. note:: The :class:`ChromeLoader` currently does not save screenshots.
    .. note:: The :class:`ChromeLoader` currently does not support single-object loading (i.e., it always loads the full page).
    .. note:: The :class:`ChromeLoader` currently does not support disabling network caches.
    .. note:: The :class:`ChromeLoader` currently does not support saving screenshots.
    '''

    def __init__(self, **kwargs):
        super(ChromeLoader, self).__init__(**kwargs)
        if not self._full_page:
            raise NotImplementedError('ChromeLoader does not support loading only an object')
        if self._disable_network_cache:
            raise NotImplementedError('ChromeLoader does not support disabling network caches.')
        if self._save_screenshot:
            raise NotImplementedError('ChromeLoader does not support saving screenshots.')

        self._xvfb_proc = None
        self._chrome_proc = None

    def _preload_objects(self, preloads, fresh):
        logging.debug('preloading objects')
        harpath = '/dev/null'
        for url in preloads:
            logging.debug('preloading %s', url)
            try:
                preload_flag = '-n'
                if fresh:
                    preload_flag = ''
                    fresh = False
                capturer_cmd = '%s -d 10 ' % CHROME_HAR_CAPTURER + preload_flag + ' -o %s %s' % (harpath, url)
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
        # path for new HAR file
        url = test['url']
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
            capturer_cmd = '%s -d 1000 ' % CHROME_HAR_CAPTURER + repeat_flag + ' -o %s %s' % (harpath, url)
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


    def _setup(self):
        stdout = self._stdout_file
        stderr = self._stdout_file

        if self._headless:
            # start a virtual display
            try:
                os.environ['DISPLAY'] = DISPLAY
                xvfb_command = '%s %s -screen 0 1366x768x24 -ac' % (XVFB, DISPLAY)
                logging.debug('Starting XVFB: %s', xvfb_command)
                self._xvfb_proc = subprocess.Popen(xvfb_command.split(),\
                    stdout=stdout, stderr=stderr)
                sleep(2)

                # check if Xvfb failed to start and process terminated
                retcode = self._xvfb_proc.poll()
                if retcode != None:
                    raise("Xvfb proc exited with return code: %i" % retcode)
            except Exception as _:
                logging.exception("Error starting XFVB")
                return False
            logging.debug('Started XVFB (DISPLAY=%s)', os.environ['DISPLAY'])

        if self._log_ssl_keys:
            keylog_file = os.path.join(self._outdir, 'ssl_keylog')
            os.environ['SSLKEYLOGFILE'] = keylog_file


        # launch chrome with no cache and remote debug on
        try:
            # TODO: enable HTTP2
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
            options += ' about:blank --remote-debugging-port=9222 --enable-benchmarking --enable-net-benchmarking --disk-cache-dir=/dev/null'

            chrome_command = '%s %s' % (CHROME, options)
            logging.debug('Starting Chrome: %s', chrome_command)
            self._chrome_proc = subprocess.Popen(chrome_command.split(),\
                stdout=stdout, stderr=stderr)
            sleep(5)

            # check if Xvfb failed to start and process terminated
            retcode = self._chrome_proc.poll()
            if retcode != None:
                raise("Chrome proc exited with return code: %i" % retcode)
        except Exception as _:
            logging.exception("Error starting Chrome")
            return False
        logging.debug('Started Chrome')
        return True


    def _teardown(self):
        if self._chrome_proc:
            logging.debug('Stopping Chrome')
            self._chrome_proc.kill()
            self._chrome_proc.wait()

        # kill any subprocesses chrome might have opened
        try:
            subprocess.check_output('killall chrome'.split())
        except Exception as e:
            logging.warning('Problem killing all chrome processes (maybe there were none): %s', e)

        if self._xvfb_proc:
            logging.debug('Stopping XVFB')
            self._xvfb_proc.kill()
            self._xvfb_proc.wait()
