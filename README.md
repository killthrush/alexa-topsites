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

Lastly, to run the app, you may use the following:

```
python main.py -k <AWS-KEY-ID> -s <AWS-SECRET-KEY>
```
