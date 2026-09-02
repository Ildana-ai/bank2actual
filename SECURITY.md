# Security

bank2actual reads bank statement files and writes CSV. It makes no network
requests in either form: the browser tool contains no fetch, XMLHttpRequest, or
beacon call, and the command-line tool imports nothing that talks to a network.
Your statements never leave your machine.

## Reporting a problem

Email **hello@ildana.ai**. Please include the bank format involved and, if you
can, a statement with the account details replaced. You will get a reply; a
confirmed issue is fixed in a new release and credited in the release notes if
you want it to be.

## What to expect from a download

Get `Bank2Actual.html` only from this repository's
[releases](https://github.com/Ildana-ai/bank2actual/releases). The file is
self-contained; a copy obtained anywhere else may have been altered.
