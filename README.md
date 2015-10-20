# Chrome webpage profiler
A browser based web test automation tool



### The test driver
```
usage: test_driver.py [-h] [-o OUTDIR] [-q] [-v] tests

Web page profiler.

positional arguments:
  tests                 A json file that describes the web page tests. See
                        README.md for details

optional arguments:
  -h, --help            show this help message and exit
  -o OUTDIR, --outdir OUTDIR
                        (obsolete) Destination directory for HAR files.
                        (default: .)
  -q, --quiet           only print errors (default: False)
  -v, --verbose         print debug info. --quiet wins if both are present
                        (default: False)
```

### The format of `tests.json`
`tests.json` has two sections:
1. `tests`: is a list of all the tests to be executed
2. `default`: shows all the default settings

Settings may appear in each test from `tests`, or in `default`.

######The following settings must be only in individual tests:
- url: the url of the page to be tested (This should not be in `default`)
- har_file_name (url): the name of saved HAR file or not
- packet_capture_file_name (url): the name of .pcap file
- preload ([]): a list of objects(urls) to be loaded in memory cache before fetching the url

######A settings parameter in `default` will be used if it is not present in a test. The settings are:
- num_trials (1): how many trials for a single test
- save_har (TRUE): save HAR file or not
- save_packet_capture (FALSE): dump traffic with tcpdump or not
- fresh_view (TRUE): clean memory cache before visiting the url or not

######The following settings are global as they will affect all of the tests. They must appear only in `default`:
- headless (TRUE): hide browser window or not
- log_ssl_keys (FALSE): dump SSL session keys or not
- disable_quic (TRUE): disable quic, force server to use TCP
- disable_spdy (FALSE): disable spdy and h2, force http/1.1
- ignore_certificate_errors (FALSE): ignore fake certs
