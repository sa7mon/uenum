#!/usr/local/Cellar/python/2.7.12/bin//python

import mmap
import argparse
import threading
import json
import requests
from collections import OrderedDict
import logging
from itertools import *
import tqdm

#######################
#                     #
#       CONFIG        #
#                     #
#######################

# Default log file name
logFileName = "./log.txt"

# Default number of threads to use if arg isn't supplied
defaultThreadLimit = 10

# Default location of config file
configFile = "config.json"


########################
#                      #
#       FUNCTIONS      #
#                      #
########################


def logPrint(msg, logLevel):
    tqdm.tqdm.write(msg)
    if logLevel == "INFO":
        log.info(msg)
    if logLevel == "DEBUG":
        log.debug(msg)

def mapcount(filename):
    """ Uses mmap to quickly count the number of lines in a text file. 
    https://stackoverflow.com/a/850962

    Args:
        filename (str): Name of file containing lines to count

    Returns:
        int: Total number of lines in text file

    """
    f = open(filename, "r+")

    buf = mmap.mmap(f.fileno(), 0)
    lines = 0
    readline = buf.readline
    while readline():
        lines += 1
    return lines


def printBanner():
    """
        # figlet -f isometric1 "uEnum"

    """
    banner = """
      ___           ___           ___           ___           ___
     /\__\         /\  \         /\__\         /\__\         /\__\\
    /:/  /        /::\  \       /::|  |       /:/  /        /::|  |
   /:/  /        /:/\:\  \     /:|:|  |      /:/  /        /:|:|  |
  /:/  /  ___   /::\~\:\  \   /:/|:|  |__   /:/  /  ___   /:/|:|__|__
 /:/__/  /\__\ /:/\:\ \:\__\ /:/ |:| /\__\ /:/__/  /\__\ /:/ |::::\__\\
 \:\  \ /:/  / \:\~\:\ \/__/ \/__|:|/:/  / \:\  \ /:/  / \/__/~~/:/  /
  \:\  /:/  /   \:\ \:\__\       |:/:/  /   \:\  /:/  /        /:/  /
   \:\/:/  /     \:\ \/__/       |::/  /     \:\/:/  /        /:/  /
    \::/  /       \:\__\         /:/  /       \::/  /        /:/  /
     \/__/         \/__/         \/__/         \/__/         \/__/
        """
    tqdm.tqdm.write(banner)


def tryUser(tUser, userNum, url, body, headers):
    """
    Send the request using the Requests library and parse the response.
    """
    resultText = " (" + str(userNum) + "/" + str(totalUsers) + ") status " + user
    # Inject actual username into args
    url = url.replace("$USERNAME", tUser)

    # Create a new OrderedDict instance because for some reason, modifying the one passed
    # modifies the global requestBody. Don't know why, I'm probably missing something obvious.
    tryBody = OrderedDict()
    for i in range(0, len(body)):
        key = body.keys()[i]
        tryBody[key] = body[key].replace("$USERNAME", tUser)

    try:
        r = requests.post(url, data=tryBody, headers=headers)
    except (AttributeError, requests.exceptions.ConnectionError) as err:
        log.error("Caught Error: " + str(err))
        return
        
    response = r.text

    if badResponse in r.text:
        resultText = resultText.replace("status", "[Bad]")
    elif goodResponse in r.text:
        resultText = resultText.replace("status", "[Good]")
    else:
        resultText += " UNKNOWN\n" + response

    log.info(resultText)
    tryBody = None


class bruteThread (threading.Thread):
    def __init__(self, user, userNum, url, body, headers):
        threading.Thread.__init__(self)
        self.user = user
        self.userNum = userNum
        self.url = url
        self.body = body
        self.headers = headers

    def run(self):
        tryUser(self.user, self.userNum, self.url, self.body, self.headers)


class OrderedHeaders(object):

    def __init__(self, *headers):
        self.headers = headers

    def items(self):
        return iter(self.headers)


class TqdmLoggingHandler (logging.Handler):
    def __init__(self, level=logging.NOTSET):
        super(self.__class__, self).__init__(level)

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.tqdm.write(msg)
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)  


########################
#                      #
#         MAIN         #
#                      #
########################

printBanner()

exitFlag = 0

# Instantiate the parser
parser = argparse.ArgumentParser(description="uEnum - A customizable user enumerator")

# Declare arguments
parser.add_argument("usersFile", help='File with usernames/emails to try')
parser.add_argument('-l', '--logfile', required=False, help='Name of log file. Default: log.txt')
parser.add_argument('-r', '--user', required=False, help='Optional user to resume at')
parser.add_argument('-t', '--threads', type=int, required=False, help='Number of threads to use. Default: 10')
parser.add_argument('-s', '--site', required=True, help='Name of site set in config.json')
parser.add_argument('-v', "--verbose", action="store_true", required=False, help='Enable verbose logging. '
                    'Useful for debugging.')

# Parse the args
args = parser.parse_args()
if args.logfile:
    logFileName = args.logfile

resumeUser = ""
if args.user:
    resumeUser = args.user

threadLimit = defaultThreadLimit
if args.threads:
    threadLimit = args.threads

# logging.addLevelName(100, "all")

# Create logger
log = logging.getLogger('uEnum')
log.setLevel(logging.DEBUG)    # Log level for console?

# Create file handler which logs even debug messages
fh = logging.FileHandler(logFileName)
fh.setLevel(logging.DEBUG)
# Create console handler with a higher log level
ch = logging.StreamHandler()
if args.verbose:
    ch.setLevel(logging.DEBUG)
else:
    ch.setLevel(logging.ERROR)

# Create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s', "%Y-%m-%d %H:%M:%S")
ch.setFormatter(formatter)
fh.setFormatter(formatter)
# Add the handlers to logger
log.addHandler(fh)

# If verbose, we want the logs to go through Tqdm.write so it doesn't mess up the progress bar.
# Otherwise, we just log normally. If errors pop up, they'll probably interrupt the bar but we've got bigger issues.
if args.verbose:
    log.addHandler(TqdmLoggingHandler())
else:
    log.addHandler(ch)

# Parse config file
targetUrl = None
goodResponse = None
badResponse = None
requestHeaders = None
requestBody = None

with open(configFile) as f:
    config = json.load(f, object_pairs_hook=OrderedDict)  # OrderedDict maintains JSON order of keys

    for i in range(0, len(config)):
        if config[i]["name"] == args.site:
            targetUrl = config[i]["targetUrl"]
            goodResponse = config[i]["goodResponse"]
            badResponse = config[i]["badResponse"]
            requestBody = config[i]["request-body"]
            requestHeaders = config[i]["request-headers"]

            log.debug("targetUrl: " + str(targetUrl))
            log.debug("goodResponse: " + str(goodResponse))
            log.debug("badResponse: " + str(badResponse))
            log.debug("requestHeaders: " + str(requestHeaders))
            log.debug("requestBody: " + str(requestBody))
            continue


# log.info("Using " + str(threadLimit) + " threads")
logPrint("Using " + str(threadLimit) + " threads", "INFO")
logPrint("Counting total users to try...", "INFO")
totalUsers = mapcount(args.usersFile)
logPrint("Users: " + str(totalUsers), "INFO")

if resumeUser:
    log.info("Searching for resume point...")

if threadLimit > totalUsers:
    log.warning("\n Warning: Using more threads than there are users will cause problems!")

# Create progress bar 
pbar = tqdm.tqdm(total=totalUsers, unit="User", unit_scale=True, dynamic_ncols=True, smoothing=0.8)

foundResumeUser = False

# e will be our counter of processed users
e = 0

# Instantiate our array of threads. We'll be appending them inside the for-loop
threads = []

with open(args.usersFile, 'r') as f:
    groupIndex = 0
    while groupIndex < totalUsers/threadLimit:  # For every group of (threadLimit) ....
        
        for user in islice(f, threadLimit):  # For each user in the chunk ....
            user = user.rstrip()             # Strip whitespace

            # If we're given a resumeUser and we haven't found it yet
            if resumeUser != "" and not foundResumeUser:
                if resumeUser == user:
                    foundResumeUser = True
                    log.info(" Found resume point!")
                else:
                    log.info(" Skipping...")
            else:
                # print("Passing requestBody from forLoop: " + str(requestBody))
                thread1 = bruteThread(user, e, targetUrl, requestBody, requestHeaders)
                thread1.start()
                threads.append(thread1)
            e += 1  

            # Update progress bar
            percentage = (float(e)/float(totalUsers))
            pbar.update(2*percentage)
            # pbar.update(e)

        # Wait for all threads to complete
        for t in threads:
            t.join()
        groupIndex += 1

    f.close()
pbar.update(100)
