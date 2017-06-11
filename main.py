import os, sys
import attr
import urllib.parse, urllib.request
import asyncio, aiohttp, async_timeout
import getopt
import json, datetime, re
import hashlib, base64, hmac
from xml.etree.ElementTree import ElementTree, fromstring
from bs4 import BeautifulSoup
from timer import EventLoopTimer


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
        self.CACHE_LOCATION = '{app_dir}/temp/alexa-data-{year}-{month}-{day}.json'
        self.TOTAL_SITES_TO_PROCESS = 1000
        self.BATCH_SIZE = 50 # The number of sites to query concurrently
        self.SITES_PER_PAGE = 100 # 100 is the default (and max) page size for Alexa Top Sites
        self.ASYNC_TIMEOUT_SECONDS = 10
        self.page_rank_heap = []
        self.aws_key_id = aws_key_id
        self.aws_secret_key = aws_secret_key
        self.event_loop = asyncio.get_event_loop()
        self.overall_stats = self.OverallStats()

    @attr.s
    class SiteStats(object):
        domain_name = attr.ib()
        duration_in_ms = attr.ib()
        word_count = attr.ib()
        word_count_ranking = attr.ib(default=None)

    @attr.s
    class OverallStats(object):
        average_word_count = attr.ib(default=None)
        duration_in_ms = attr.ib(default=None)
        site_stats = attr.ib(default=attr.Factory(list))
        header_stats = attr.ib(default=attr.Factory(dict))
        error_list = attr.ib(default=attr.Factory(list))

    @attr.s
    class HeaderStats(object):
        site_count = attr.ib(default=0)
        percentage = attr.ib(default=0.0)

    @attr.s
    class ErrorItem(object):
        domain_name = attr.ib()
        error_message = attr.ib()

    def run(self):
        """
        Runs the Alexa Site Analyzer and returns site metadata in a structured format.

        Args:
            None

        Returns:
            An instance of OverallStats which contains the desired information (see class docs)
        """
        with EventLoopTimer(self.event_loop) as stopwatch:
            domains = self._get_top_site_domains()
            print('Processing {} unique domains...'.format(len(domains)))

            # Performance gets a little weird when trying to do hundreds of concurrent requests.
            # It seems to be a lot more stable (and faster overall) to batch the requests into smaller groups.
            for batch_num in range(0, int(self.TOTAL_SITES_TO_PROCESS / self.BATCH_SIZE)):
                begin_index = 0 + (batch_num * self.BATCH_SIZE)
                end_index = self.BATCH_SIZE + begin_index
                self.event_loop.run_until_complete(self._query_top_sites(domains[begin_index:end_index]))

        # Process overall stats
        word_count_sum = 0
        sites_sorted_by_word_count = sorted(self.overall_stats.site_stats, key=lambda x: x.word_count, reverse=True)
        for i, site in enumerate(sites_sorted_by_word_count):
            site.word_count_ranking = 1 + i
            word_count_sum += site.word_count
        self.overall_stats.average_word_count = word_count_sum / self.TOTAL_SITES_TO_PROCESS
        self.overall_stats.duration_in_ms = stopwatch.interval * 1000

        # Note that if I sum the duration of the individual scans, the often don't match
        # the duration of the overall scan.  They're in the ballpark but off by just enough to
        # make me think that I'm doing something wrong somehwere.
        expected_sum = sum([site.duration_in_ms for site in self.overall_stats.site_stats])
        print('Expected MS: {}'.format(expected_sum))
        print('Overall count of sites (minus errors): {}'.format(len(sites_sorted_by_word_count)))
        print('Overall count of errors: {}'.format(len(self.overall_stats.error_list)))
        return self.overall_stats

    async def _process_site(self, session, url):
        """
        Using an async-friendly web client, query a given site and
        return its content HTML and headers along with its duration and any errors.

        Args:
            session: An open aiohttp client that will be used to query the site
            url: The URL to query

        Returns:
            Asynchronously returns a 5-tuple: (url, HTML content, header collection, error message, duration)
        """
        page_text, response_headers, error_message, duration = (None,) * 4
        try:
            with async_timeout.timeout(self.ASYNC_TIMEOUT_SECONDS):
                # Attempt to fool the bot-blockers...
                headers = {
                    'User-Agent': (
                        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko)'
                        'Chrome/35.0.1916.47 Safari/537.36'
                    )
                }
                print('Making request for {}'.format(url))
                async with session.get(url, headers=headers) as response:
                    with EventLoopTimer(self.event_loop) as stopwatch:
                        page_text = await response.text(encoding='utf-8')
                        response_headers = response.headers
                        print('Got response for {}'.format(url))
                    duration = stopwatch.interval * 1000
        except Exception as e:
            print(e)
            error_message = str(e)
        return url, page_text, response_headers, error_message, duration

    async def _query_top_sites(self, domains):
        """
        Using an event loop, query the Top Sites in parallel and record some stats.

        Args:
            domains: A list of domain names of a number of top sites to analyze

        Returns:
            None
        """
        tasks = []
        async with aiohttp.ClientSession(loop=self.event_loop) as session:
            for domain in domains:
                url = 'http://{}'.format(domain)
                task = self.event_loop.create_task(self._process_site(session, url))
                task.add_done_callback(self._analyze_site_output)
                tasks.append(task)
                print('Created task for {}'.format(url))
            await asyncio.wait(tasks)

    def _analyze_site_output(self, future):
        """
        Callback function for the task that fetches data from one of the top sites.

        Args:
            future: The resolved future object that should contain the results of the task.
                    Might not have values in it due to things like connection errors.

        Returns:
            None
        """
        url, content, headers, error, request_duration = future.result()
        if not content or not headers:
            print('Processing error response for {}'.format(url))
            error_item = self.ErrorItem(domain_name=url, error_message=error)
            self.overall_stats.error_list.append(error_item)
            return
        print('Loaded valid response for {}'.format(url))

        scan_duration = request_duration
        with EventLoopTimer(self.event_loop) as stopwatch:
            soup = BeautifulSoup(content, 'html.parser')
            [s.extract() for s in soup('script')]
            [s.extract() for s in soup('style')]
            text = soup.get_text().strip()
            words = re.split('\s+', text)

            for header in set(headers):
                stats = self.overall_stats.header_stats.get(header)
                if not stats:
                    stats = self.HeaderStats()
                stats.site_count += 1
                stats.percentage = float(stats.site_count) / float(self.TOTAL_SITES_TO_PROCESS) * 100.0
                self.overall_stats.header_stats[header] = stats
        scan_duration += stopwatch.interval * 1000
        site_stats = self.SiteStats(domain_name=url, duration_in_ms=scan_duration, word_count=len(words))
        self.overall_stats.site_stats.append(site_stats)

    def _create_alexa_topsite_request_url(self, page_num):
        """
        Constructs a request to the AWS Alexa Top Sites Service.
        The process includes a signature; this mechanism is documented here:
        http://docs.aws.amazon.com/AlexaTopSites/latest/

        Args:
            page_num: Each request must include a record offset, since only 100
                      records may be returned at one time from the service. This
                      page number allows us to compute the appropriaate offset.

        Returns:
            A string containing the full absolute URL of a valid Top Sites request
        """
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

    def _parse_site_info_from_xml(self, xml):
        """
        Given XML in the Top Sites format, pull out the domains of the sites and return
        them all in rank order.

        Args:
            xml: The input XML (format is here:
                 https://docs.aws.amazon.com/AlexaTopSites/latest/index.html?ApiReference_TopSitesAction.html)

        Returns:
            A list(unicode) containing domain name of the top sites
        """
        namespace = {
            'aws': 'http://ats.amazonaws.com/doc/2005-11-21'
        }
        tree = ElementTree(fromstring(xml))
        root = tree.getroot()
        domain_list = []
        sites_xpath = 'aws:Response/aws:TopSitesResult/aws:Alexa/aws:TopSites/aws:Country/aws:Sites'
        sites_element = root.find(sites_xpath, namespace)
        for site_node in sites_element.findall('aws:Site', namespace):
            domain = site_node.find('aws:DataUrl', namespace).text
            domain_list.append(domain)
        return domain_list

    def _get_top_site_domains(self):
        """
        Attempt to load the domain list of Alexa Top Sites either from a local copy
        or from calling AWS.

        Args:
            None

        Returns:
            A list of domain name strings.
        """
        now = datetime.datetime.utcnow()
        params = {
            'app_dir': os.path.dirname(os.path.realpath(__file__)),
            'year': now.year,
            'month': now.month,
            'day': now.day,
        }
        cache_filename = self.CACHE_LOCATION.format(**params)
        all_domains = []
        if os.path.exists(cache_filename):
            print('Loading domain list from cache: {}'.format(cache_filename))
            with open(cache_filename, 'r') as cache_file:
                all_domains = json.loads(cache_file.read())
        else:
            print('Loading domain list from AWS...')
            num_pages = int(self.TOTAL_SITES_TO_PROCESS / self.SITES_PER_PAGE)
            for page_num in range(1, num_pages + 1):
                url = self._create_alexa_topsite_request_url(page_num)
                print('Querying Top Sites Service: {}'.format(url))
                with urllib.request.urlopen(url) as response:
                   xml_data = response.read().decode("utf-8")
                domains = self._parse_site_info_from_xml(xml_data)
                all_domains += domains
            os.makedirs(os.path.dirname(cache_filename))
            with open(cache_filename, 'w') as cache_file:
                cache_file.write(json.dumps(all_domains))
        return all_domains


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
    output = analyzer.run()
    print(attr.asdict(output))
    print('quitting!')

if __name__ == '__main__':
    process_command_line(sys.argv)
