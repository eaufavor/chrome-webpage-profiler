#!/usr/bin/env python

import os
import sys
import logging
import argparse
import pprint
from chrome_loader import ChromeLoader

def main():
    #loader = NodeJsLoader(num_trials=1, full_page=False, http2=True)
    #loader = CurlLoader(num_trials=1, full_page=False)
    #loader = PythonRequestsLoader(num_trials=1)
    #loader = FirefoxLoader(num_trials=1, headless=False, selenium=False)
    #loader = PhantomJSLoader(num_trials=5)
    #loader = TCPLoader(num_trials=2, full_page=False, user_agent='Test User Agent', check_protocol_availability=False)
    #loader = TLSLoader(num_trials=2, full_page=False, test_session_resumption=True, timeout=10)
    #loader = TLSLoader(num_trials=2, full_page=False, test_false_start=True, timeout=10)
    loader = ChromeLoader(num_trials=2, disable_quic=True, disable_spdy=False, check_protocol_availability=False,\
        save_packet_capture=True, log_ssl_keys=True, save_har=True, disable_local_cache=False, headless=False, ignore_certificate_errors=True)
    #loader.load_pages(['https://http2.akamai.com/demo'])
    loader.load_pages(['https://www.forever21.com'])
    print loader.urls
    pprint.pprint(dict(loader.load_results))
    #pprint.pprint(dict(loader.page_results))

if __name__ == "__main__":
    # set up command line args
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                                     description='Web page profiler.')
    parser.add_argument('-o', '--outdir', default='.', help='Destination directory for HAR files.')
    parser.add_argument('-q', '--quiet', action='store_true', default=False, help='only print errors')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='print debug info. --quiet wins if both are present')
    args = parser.parse_args()

    if not os.path.isdir(args.outdir):
        try:
            os.makedirs(args.outdir)
        except Exception as e:
            logging.getLogger(__name__).error('Error making output directory: %s' % args.outdir)
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

    main()
