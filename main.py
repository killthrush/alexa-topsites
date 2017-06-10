import os
import sys
import attr
import urllib.parse
import urllib.request
import getopt
import asyncio
import heapq
import json
import datetime
import hashlib
import base64
import hmac
from bs4 import BeautifulSoup


class AlexaSiteAnalyzer(object):
    """
    Using the Alexa Top Sites API, compute the following for the top N sites:

        Per Site
            Word count of the first page and rank across all the sites based off the word count
            Duration of the scan
        Across All Sites
            AVG word count of the first page
            Top 20 HTTP headers and the percentage of sites they were seen in
            Duration of the entire scan

    This object will attempt to cache the output of the API to a local file
    in order to avoid unnecessary request charges; as of this writing each URL
    costs $.0025 to process.
    """

    def __init__(self, aws_key_id, aws_secret_key):
        self.CACHE_LOCATION = '{app_dir}/temp/alexa-data-{yyyy}-{mm}-{dd}.json'
        self.TOTAL_SITES_TO_PROCESS = 1000
        self.SITES_PER_PAGE = 100 # 100 is the default (and max) page size for Alexa Top Sites
        self.global_site_counter = 0
        self.page_rank_heap = []
        self.aws_key_id = aws_key_id
        self.aws_secret_key = aws_secret_key

    @attr.s
    class SiteStats(object):
        process_count = attr.ib()
        duration_in_ms = attr.ib()
        word_count = attr.ib()
        word_count_ranking = attr.ib(default=None)

    @attr.s
    class OverallStats(object):
        average_word_count = attr.ib()
        duration_in_ms = attr.ib()
        site_stats = attr.ib(default=attr.Factory)

    @attr.s
    class HeaderStats(object):
        header_name = attr.ib()
        percentage = attr.ib()

    def run(self):
        """
        Runs the Alexa Site Analyzer and returns metadata in a structured format.
        Returns:

        """
        pass

    def _create_alexa_topsite_request_url(self, page_num):

        signature_template = (
            'GET\n'
            'ats.amazonaws.com\n'
            '/\n'
            '{url}'
        )

        params = {
            'AWSAccessKeyId': self.aws_key_id,
            'Action': 'TopSites',
            'Count': self.TOTAL_SITES_TO_PROCESS,
            'CountryCode': 'US',
            'ResponseGroup': 'Country',
            'SignatureMethod': 'HmacSHA256',
            'SignatureVersion': 2,
            'Start': self.SITES_PER_PAGE * (page_num - 1) + 1,
            'Timestamp': datetime.datetime.utcnow().isoformat(),
        }
        querystring = urllib.parse.urlencode(params)

        base_url = 'http://ats.amazonaws.com/?{}'.format(querystring)
        signature = signature_template.format(url=querystring).encode('utf-8')
        secret = self.aws_secret_key.encode('utf-8')
        digest = hmac.new(secret, msg=signature, digestmod=hashlib.sha256).digest()
        encoded_signature = urllib.parse.urlencode({'Signature': base64.b64encode(digest)})
        signed_url = '{}&{}'.format(base_url, encoded_signature)
        return signed_url

    def _parse_site_info_from_xml(self):
        pass

    def _fetch_top_sites_xml(self, ):
        """
        Attempt to load the Alexa Top Sites XML either from a local copy
        or from calling AWS.
        Returns: A string of XML data containing sites.
        """
        now = datetime.datetime.utcnow()
        params = {
            'app_dir': os.path.dirname(os.path.realpath(__file__)),
            'year': now.year,
            'month': now.month,
            'day': now.day,
        }
        cache_filename = self.CACHE_LOCATION.format(**params)
        site_data = None
        if os.path.exists(cache_filename):
            with open(cache_filename, 'r') as cache_file:
                site_data = json.loads(cache_file.read())
        else:
            num_pages = self.TOTAL_SITES_TO_PROCESS / self.SITES_PER_PAGE
            for page_num in range(1, num_pages + 1):
                url = self._create_alexa_topsite_request_url(page_num)

        return site_data


# on startup, check for local cached file
# if no cached file, prepare to do main loop
# with a timer, grab 1000 top sites
    # parse xml, fetch data from the 1000 sites in parallel using asyncio
    # each request is timed
    # count words using beautiful soup, create stats record, and add to the ranking heap
# record overall site stats, create site ranking and return results


def process_command_line(all_args):
    """
    Parses command-line options and runs the analyzer

    Args:
        all_args: The set of all command-line args to process

    Returns: None

    """
    try:
        opts, args = getopt.getopt(all_args[1:], 'hk:s:', ['aws-key-id=', 'aws-secret-key='])
    except getopt.GetoptError:
        print('main.py [-h] -k <AWS-KEY-ID> -s <AWS-SECRET-KEY>')
        sys.exit(2)

    aws_key_id = None
    aws_secret_key = None
    for opt, arg in opts:
        if opt == '-h':
            print('main.py [-h] -k <AWS-KEY-ID> -s <AWS-SECRET-KEY>')
            sys.exit()
        elif opt in ("-k", "--aws-key-id"):
            aws_key_id = arg
        elif opt in ("-s", "--aws-secret-key"):
            aws_secret_key = arg

    analyzer = AlexaSiteAnalyzer(aws_key_id=aws_key_id, aws_secret_key=aws_secret_key)

    # Test the URL gen & signing
    print(analyzer._create_alexa_topsite_request_url(3))


if __name__ == '__main__':
    process_command_line(sys.argv)
