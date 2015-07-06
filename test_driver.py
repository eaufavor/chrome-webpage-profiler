#!/usr/bin/env python

import os
import sys
import logging
import argparse
import pprint
import json
from chrome_loader import ChromeLoader

GLOBAL_DEFAULT = {'headless': True, 'log_ssl_keys': False, 'disable_quic': True,
                  'disable_spdy': False, 'ignore_certificate_errors': False}
LOCAL_DEFAULT = {'num_trials': 1, 'save_har': True, 'save_packet_capture': False,
                 'fresh_view': True}
PRIVATE_DEFAULT = {'har_file_name': None, 'packet_capture_file_name': None}

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


def main(fileName):

    with open(fileName, 'r') as f:
        tests = json.load(f)
    prepare_tests_settings(tests)
    default = tests['default']

    loader = ChromeLoader(disable_quic=default['disable_quic'], disable_spdy=default['disable_spdy'],
                          check_protocol_availability=False, save_packet_capture=True,
                          log_ssl_keys=default['log_ssl_keys'], save_har=True, disable_local_cache=False,
                          headless=default['headless'], ignore_certificate_errors=default['ignore_certificate_errors'])
    #loader.load_pages(['https://http2.akamai.com/demo'])

    #loader.load_pages(['https://www.forever21.com'])
    print tests
    loader.load_pages(tests)
    print loader.urls
    pprint.pprint(dict(loader.load_results))
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
