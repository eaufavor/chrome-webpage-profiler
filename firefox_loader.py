import os
import subprocess
import logging
import tempfile
import platform
from time import sleep
from loader import Loader, LoadResult, Timeout, TimeoutError
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait # available since 2.4.0
import glob

FIREFOX = '/usr/bin/env firefox' if platform.system() != 'Darwin' else\
    '/Applications/Firefox.app/Contents/MacOS/firefox'
XVFB = '/usr/bin/env Xvfb'
DISPLAY = ':%s'%os.geteuid()


fireBugPath = os.path.join(os.path.dirname(__file__), './plugins/firebug-2.0.11.xpi')
netExportPath = os.path.join(os.path.dirname(__file__), './plugins/netExport-0.9b7.xpi')
fireStarterPath = os.path.join(os.path.dirname(__file__), './plugins/fireStarter-0.1a6.xpi')

TIMINGS_JAVASCRIPT = '''
var performance = window.performance || {};
var timings = performance.timing || {};
return timings;
'''

# TODO: send firefox output to separate log file
# TODO: disable network cache (send header)


class FirefoxLoader(Loader):
    '''Subclass of :class:`Loader` that loads pages using Firefox.

    .. note:: The :class:`FirefoxLoader` currently does not extract HARs.
    .. note:: The :class:`FirefoxLoader` currently does not save screenshots.
    .. note:: The :class:`FirefoxLoader` currently does not support single-object loading (i.e., it always loads the full page).
    .. note:: The :class:`FirefoxLoader` currently does not support disabling network caches.
    .. note:: The :class:`FirefoxLoader` currently does not support saving screenshots.
    '''

    def __init__(self, selenium=True, **kwargs):
        super(FirefoxLoader, self).__init__(**kwargs)
        if not self._full_page:
            raise NotImplementedError('FirefoxLoader does not support loading only an object')
        if self._disable_network_cache:
            raise NotImplementedError('FirefoxLoader does not support disabling network caches.')
        #if self._save_har:
        #   raise NotImplementedError('FirefoxLoader does not support saving HARs')
        #if self._save_screenshot:
        #   raise NotImplementedError('FirefoxLoader does not support saving screenshots')

        self._selenium = selenium
        self._xvfb_proc = None
        self._firefox_proc = None
        self._profile_name = 'webloader'
        self._profile_path = os.path.join(tempfile.gettempdir(),\
            'webloader_profile')
        self._selenium_driver = None

    def _load_page_selenium(self, test, _, trial_num):
        # load the specified URL (with selenium)
        url = test['url']
        logging.info('Fetching page %s', url)
        if test['save_har']:
            prefix = test['har_file_name'] if test['har_file_name'] else url
            harpath = self._outfile_path(prefix, suffix='.har', trial=trial_num)

        else:
            harpath = None
        try:
            # load page
            if test['fresh_view']:
                # Start a new browser as there is no way to clear cache
                if self._selenium_driver:
                    self._selenium_driver.quit()
                self._setup_selenium()
            elif not self._selenium_driver:
                # or this is the first run, start a new browser
                self._setup_selenium()
            harfiles = glob.glob('./*.har')
            if harfiles:
                last_har = os.path.basename(max(harfiles, key=os.path.getctime))
            else:
                last_har = None

            with Timeout(seconds=self._timeout+5):
                self._selenium_driver.get(url)
                WebDriverWait(self._selenium_driver, 30000).until(\
                    lambda d: d.execute_script('return document.readyState') == 'complete')
                logging.debug('Page loaded.')

            # get timing information
            # http://www.w3.org/TR/navigation-timing/#processing-model
            timings = self._selenium_driver.execute_script(TIMINGS_JAVASCRIPT)
            load_time = (timings['loadEventEnd'] - timings['fetchStart']) / 1000.0

            count = 0
            while count < 31 - load_time:
                harfiles = glob.glob('./*.har')
                if harfiles:
                    newest = os.path.basename(max(harfiles, key=os.path.getctime))
                else:
                    newest = None
                if newest and newest != last_har:
                    break
                sleep(1)

            #find the newest har file and rename it to want we want
            harfiles = glob.glob('./*.har')
            logging.debug('Renaming harfiles: %s', str(harfiles))
            if harfiles:
                newest = os.path.basename(max(harfiles, key=os.path.getctime))
                if harpath:
                    p = subprocess.Popen(['mv', newest, harpath])
                else:
                    p = subprocess.Popen(['rm', newest])
                p.wait()

            return LoadResult(LoadResult.SUCCESS, url, time=load_time,\
                final_url=self._selenium_driver.current_url)

        except TimeoutError:
            logging.exception('* Timeout fetching %s', url)
            return LoadResult(LoadResult.FAILURE_TIMEOUT, url)
        except TimeoutException:
            logging.exception('Timeout fetching %s', url)
            return LoadResult(LoadResult.FAILURE_TIMEOUT, url)
        except Exception as e:
            logging.exception('Error loading %s: %s', url, e)
            return LoadResult(LoadResult.FAILURE_UNKNOWN, url)

    def _load_page(self, test, outdir, trial_num=-1):
        return self._load_page_selenium(test, outdir, trial_num)

    def _preload_objects(self, preloads, fresh):
        logging.debug('Preloading objects')
        if fresh:
            # Start a new browser as there is no way to clear cache
            if self._selenium_driver:
                self._selenium_driver.quit()
            self._setup_selenium()
        elif not self._selenium_driver:
            self._setup_selenium()

        for url in preloads:
            logging.debug('preloading %s', url)
            try:
                harfiles = glob.glob('./*.har')
                if harfiles:
                    last_har = os.path.basename(max(harfiles, key=os.path.getctime))
                else:
                    last_har = None

                with Timeout(seconds=self._timeout+5):
                    self._selenium_driver.get(url)
                    WebDriverWait(self._selenium_driver, 30000).until(\
                        lambda d: d.execute_script('return document.readyState') == 'complete')
                    logging.debug('object loaded.')
                    sleep(0.5)

                harfiles = glob.glob('./*.har')
                if harfiles:
                    newest = os.path.basename(max(harfiles, key=os.path.getctime))
                    if newest != last_har:
                        logging.debug('Removing harfile: %s', str(newest))
                        p = subprocess.Popen(['rm', newest])
                        p.wait()


            except TimeoutError:
                logging.exception('* Timeout fetching %s', url)
                return LoadResult(LoadResult.FAILURE_TIMEOUT, url)
            except TimeoutException:
                logging.exception('Timeout fetching %s', url)
                return LoadResult(LoadResult.FAILURE_TIMEOUT, url)
            except Exception as e:
                logging.exception('Error loading %s: %s', url, e)
                return LoadResult(LoadResult.FAILURE_UNKNOWN, url)


    def _load_page_native(self, url, _, __):
        # load the specified URL (directly)
        logging.info('Fetching page %s', url)
        try:
            firefox_cmd =  '%s %s' % (FIREFOX, url)
            #firefox_cmd =  '%s -profile %s %s' % (FIREFOX, self._profile_path, url)
            logging.debug('Loading: %s', firefox_cmd)
            with Timeout(seconds=self._timeout+5):
                subprocess.check_output(firefox_cmd.split())

            # TODO: error checking
            # TODO: try to get timing info, final URL, HAR, etc.

            logging.debug('Page loaded.')
            return LoadResult(LoadResult.SUCCESS, url)

        except TimeoutError:
            logging.exception('* Timeout fetching %s', url)
            return LoadResult(LoadResult.FAILURE_TIMEOUT, url)
        except subprocess.CalledProcessError as e:
            logging.exception('Error loading %s: %s\n%s', url, e, e.output)
            return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
        except Exception as e:
            logging.exception('Error loading %s: %s', url, e)
            return LoadResult(LoadResult.FAILURE_UNKNOWN, url)

    def _setup_selenium(self):
        # prepare firefox selenium driver
        try:
            #profile = webdriver.FirefoxProfile()
            profile = webdriver.firefox.firefox_profile.FirefoxProfile()
            profile.add_extension(fireBugPath)
            profile.add_extension(netExportPath)
            profile.add_extension(fireStarterPath)
            profile.set_preference("app.update.enabled", False)
            profile.native_events_enabled = True
            profile.set_preference("extensions.firebug.DBG_STARTER", True)
            # disable firebug start screen
            profile.set_preference("extensions.firebug.currentVersion", "2.0.11")
            profile.set_preference("extensions.firebug.addonBarOpened", True)
            profile.set_preference("extensions.firebug.net.enableSites", True)
            profile.set_preference("extensions.firebug.previousPlacement", 1)
            profile.set_preference("extensions.firebug.allPagesActivation", "on")
            profile.set_preference("extensions.firebug.onByDefault", True)
            profile.set_preference("extensions.firebug.defaultPanelName", "net")
            profile.set_preference("extensions.firebug.netexport.alwaysEnableAutoExport", True)
            profile.set_preference("extensions.firebug.netexport.autoExportToFile", True)
            profile.set_preference("extensions.firebug.netexport.saveFiles", True)
            profile.set_preference("extensions.firebug.netexport.autoExportToServer", False)
            profile.set_preference("extensions.firebug.netexport.Automation", True)
            profile.set_preference("extensions.firebug.netexport.showPreview", False)
            profile.set_preference("extensions.firebug.netexport.includeResponseBodies", False)
            profile.set_preference("extensions.firebug.netexport.exportFromBFCache", True)
            profile.set_preference("extensions.firebug.net.defaultPersist", False)
            profile.set_preference("extensions.firebug.netexport.pageLoadedTimeout", 300)
            profile.set_preference("extensions.firebug.netexport.timeout", 30000)
            profile.set_preference("extensions.firebug.netexport.defaultLogDir", os.getcwd())
            profile.update_preferences()

            """
            if self._disable_local_cache:
                profile.set_preference("browser.cache.disk.enable", False)
                profile.set_preference("browser.cache.memory.enable", False)
            if self._http2:
                # As of v34, this is enabled by default anyway
                profile.set_preference("network.http.spdy.enabled.http2draft", True)
                # Attempt to always negotiate http/2.0
                profile.set_preference("network.http.proxy.version", "2.0")
                profile.set_preference("network.http.version", "2.0")
                # Disable validation when using our testing server (since we don't own a valid cert)
                # profile.set_preference("network.http.spdy.enforce-tls-profile", False)
            """
            if self._user_agent:
                profile.set_preference("general.useragent.override", '"%s"' % self._user_agent)
            self._selenium_driver = webdriver.Firefox(firefox_profile=profile)
            sleep(1)
            # load a page other than about:blank
            self._selenium_driver.get('about:config')
        except Exception as _:
            logging.exception("Error making selenium driver")
            return False
        return True



    def _setup_native(self):
        # make firefox profile and set preferences
        try:
            # create profile
            create_cmd = '%s -CreateProfile "%s %s"'\
                % (FIREFOX, self._profile_name, self._profile_path)
            logging.debug('Creating Firefox profile: %s', create_cmd)
            subprocess.check_output(create_cmd, shell=True)

            # write prefs to user.js
            userjs_path = os.path.join(self._profile_path, 'user.js')
            logging.debug('Writing user.js: %s', userjs_path)
            with open(userjs_path, 'w') as f:
                if self._disable_local_cache:
                    f.write('user_pref("browser.cache.disk.enable", false);\n')
                    f.write('user_pref("browser.cache.memory.enable", false);\n')
                if self._http2:
                    # As of v34, this is enabled by default anyway
                    f.write('user_pref("network.http.spdy.enabled.http2draft", true);\n')
                if self._user_agent:
                    f.write('user_pref("general.useragent.override", "%s");\n' % self._user_agent)
        except Exception as _:
            logging.exception("Error creating Firefox profile")
            return False

        # launch firefox
        try:
            firefox_command =  '%s -profile %s' % (FIREFOX, self._profile_path)
            logging.debug('Starting Firefox: %s', firefox_command)
            self._firefox_proc = subprocess.Popen(firefox_command.split())
            sleep(5)
        except Exception as _:
            logging.exception("Error starting Firefox")
            return False
        logging.debug('Started Firefox')
        return True



    def _setup(self, __=0):

        if self._headless:
            # start a virtual display
            try:
                os.environ['DISPLAY'] = DISPLAY
                xvfb_command = '%s %s -screen 0 1366x768x24 -ac' % (XVFB, DISPLAY)
                logging.debug('Starting XVFB: %s', xvfb_command)
                self._xvfb_proc = subprocess.Popen(xvfb_command.split())
                sleep(2)
            except Exception as _:
                logging.exception("Error starting XFVB")
                return False
            logging.debug('Started XVFB (DISPLAY=%s)', os.environ['DISPLAY'])

        if self._log_ssl_keys:
            keylog_file = './ssl_keylog'
            os.environ['SSLKEYLOGFILE'] = keylog_file

        return True

    def _teardown(self):
        if self._selenium_driver:
            try:
                self._selenium_driver.quit()
            except Exception as e:
                logging.error('Failed to kill selenium, %s', e)
        if self._firefox_proc:
            logging.debug('Stopping Firefox')
            self._firefox_proc.terminate()
            self._firefox_proc.wait()
        if self._xvfb_proc:
            logging.debug('Stopping XVFB')
            self._xvfb_proc.terminate()
            self._xvfb_proc.wait()

        ## remove the firefox profile
        #try:
        #    shutil.rmtree(self._profile_path)
        #except Exception as e:
        #    logging.exception('Error removing firefox profile: %s' % e)
