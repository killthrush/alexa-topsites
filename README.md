# Alexa Top Sites Analyzer
A sample python 3 app for interacting with Amazon's Alexa Top Sites service.

# Installation and Setup

First, you'll need to set up an AWS account and get your key ID and secret key.  They will be needed as inputs to the program.  NOTE: keys created for an IAM user are not supported for this service and *will not work*! You will need to generate keys for your AWS root account, even though this is goes against recommended best practices.  See [this article](https://stackoverflow.com/questions/27238694/signaturedoesnotmatch-response-from-aws-of-alexa-top-sites-service) for details.

Next, with your AWS root account, you'll need to opt-in to the Alexa Top Sites service using [this site](https://aws.amazon.com/alexa-top-sites/).

Then, clone the repo and set up the app.  This assumes you already have Python 3.6 installed somewhere on your system.  Run the following commands to do this:

```
git clone git@github.com:killthrush/alexa-topsites
cd alexa-topsites
python3 -m venv venv
source venv/bin/activate
venv/bin/pip install -U -r requirements.txt
```

Lastly, to run the app, you may use the following from the root of the repo:

```
python src/main.py -k <AWS-KEY-ID> -s <AWS-SECRET-KEY>
```

# Discussion

A few interesting points and observations:
1. That IAM issue mentioned in the Setup section above was a real gotcha.  For a long time I thought I was just not following the signing process properly, but it just turned out to be rejecting my account because the service wasn't supported except by Root.
1. This was my first attempt to use python 3.6 for a project.  Several things were tricky, but were solvable: making sure to use `pip` from inside `venv` e.g. `venv/bin/pip install` vs `pip install`.  On my setup, this made a difference.  Also, my version of pycharm 5 did not support `async/await` syntax, so I needed to grab a free trial of the latest version.
1. Asyncio is awesome.  Very similar to using promises/generators in javascript and the TPL in C#.NET.  But there's just enough different to make things interesting.  This analyzer is a good use case for a high degree of parallelism.
1. A few of the domains on the list seemed to be unreachable for some reason.  A few also time out regularly, and some also have encodings that don't seem compatible with utf-8.  But most of the sites work just fine.  If this was production code, I'd probably dig in a bit more on the edge cases.
1. There's a staggering number of headers out there in the wild.  There are plenty of the usual suspects (like `Content-Type`) but a long tail of `X-` style custom headers that do who knows what.
1. Calculating time with async is tricky.  I left some comments in the code - adding up all the scan durations gives me a different answer in terms of milliseconds.  It's in the right ballpark, but it's off by just enough to make me scratch my head and wonder what I'm doing wrong.
1. Overall, the asyncio approach works well to make this a pretty fast scan - it takes between 2-3 minutes on average.