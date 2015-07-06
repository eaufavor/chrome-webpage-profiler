### The format of `tests.json`
`tests.json` has two sections:
1. `tests`: is a list of all the tests to be executed
2. `default`: shows all the default settings

Settings may appear in each test from `tests`, or in `default`.

######The following settings must be only in individual tests:
- url: the url of the page to be tested (This should not be in `default`)
- har_file_name (url): the name of saved HAR file or not
- packet_capture_file_name (url): the name of .pcap file

######A settings parameter in `default` will be used if it is not present in a test. The settings are:
- num_trails (1): how many trails for a single test
- save_har (TRUE): save HAR file or not
- save_packet_capture (FALSE): dump traffic with tcpdump or not
- fresh_view (TRUE): clean memory cache before visiting the url or not

######The following settings are global as they will affect all of the tests. They must appear only in `default`:
- headless (TRUE): hide browser window or not
- log_ssl_keys (FALSE): dump SSL session keys or not
- disable_quic (TRUE): disable quic, force server to use TCP
- disable_spdy (FALSE): disable spdy and h2, force http/1.1
- ignore_certificate_errors (FALSE): ignore fake certs
