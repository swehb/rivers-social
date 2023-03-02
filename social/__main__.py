from rich import print
from datetime import datetime, timezone
import social.data.test_tweets as test_tweets
from dateutil import parser  #  pip install python-dateutil --upgrade
import os
import tweepy
import openai
import praw

# environ must be loaded before rivertils
import dotenv
dotenv.load_dotenv(override=True)

from rivertils.rivertils import get_test_message_and_language
import random
import argparse

print("Running social.py")

parser = argparse.ArgumentParser()
parser.add_argument('--test', "-t", action=argparse.BooleanOptionalAction)
# parser.add_argument("-c", "--count", help="number of tweets to fetch", type=int, default=25)
parser.add_argument("-m", "--mode", help="which routine to run", type=str, choices=["twittermentions", "twittertimeline", "reddit", "insta"], default="twittermentions")

args = parser.parse_args()
test = args.test
# count = args.count
mode = args.mode

if test:
    print("TESTING MODE")

else:
    print("LIVE MODE")

# twitter_yoda = "respond to this twitter mention as if you are Rivers Cuomo from Weezer, but using the language of Yoda. Make it funny."
# twitter_spicoli = "respond to this twitter mention as if you are Rivers Cuomo from Weezer, but using the language of Spicoli from Fast Times at Ridgemont High. Make it funny."
# twitter_gollum = "respond to this twitter mention as if you are Rivers Cuomo from Weezer, but using the language of Gollum from The Hobbit. Make it funny."
# twitter_santa= "respond to this twitter mention as if you are Rivers Cuomo from Weezer mixed with Santa Claus. Make it funny."
# twitter_prompts = [twitter_prompt, twitter_yoda, twitter_spicoli, twitter_gollum]

character = input("which character do you want to use? (default is 'Rivers Cuomo from Weezer')") or "Rivers Cuomo from Weezer"
emotion = input("what emotion do you want the bot to have? (default is 'funny')") or "funny"

# get the last context from the text file
with open("social/last_context.txt", "r") as f:
    last_context = f.read()

# will ignore any input containing these words
# get the last context from the text file
with open("social/bads.txt", "r") as f:
    bads = f.read()
print("bads: ", bads)

context = input(f"any additional context you wish to give the bot about itself? (for example, '{last_context}')") or ""

if context != "":

    # save the ids of the tweet to a text file
    with open("social/last_context.txt", "w") as f:

        f.write(context)

base_prompt = f"respond to this {mode} comment as if you are {character}. Your response should use current slang and should be {emotion}."
twitter_prompts = [base_prompt]

def build_openai_response(text: str, prompt: str):

    prompt = f"{prompt}.\nHere is the text I want you to respond to: '{text}'"
    # print(prompt)

    reply = openai.Completion.create(
        model="text-davinci-003",
        prompt=prompt,
        temperature=1,
        max_tokens=120,
    )
    reply = reply["choices"]
    reply = reply[0]["text"]
    reply = reply.replace("\n\n", "\n")
    reply = reply.replace('"', "")
    reply = reply.replace("2020", "2023")
    reply = reply.replace("2021", "2023")
    reply = reply.strip()
    # print(reply)
    return reply


def sub(s):
    bads = [
        # "@RiversCuomo", 
        # "@Weezer", 
        
        "GenZ",
        "Gen-Z",
     ]
    goods = ["lit", "based"]
    for b in bads:
        s = s.replace(b,random.choice(goods))
    return s


def finalize_response(response: str, language: str):
    """
    Returns a string.
    Replace any names with the user's name. Translate the reponse to the user's language of choice. Append punctuation.
    """

    # if language and language != "en":
    #     blob = TextBlob(response)
    #     # print(blob)

    #     try:
    #         response = blob.translate(to=language).raw
    #     except Exception as e:
    #         print("Couldn't do blob.translate in finalize_reponse: ", e, blob)


    # if language and language != "en":
    #     blob = TextBlob(response)
    #     # print(blob)

    #     try:
    #         response = blob.translate(to=language).raw
    #     except Exception as e:
    #         print("Couldn't do blob.translate in finalize_reponse: ", e, blob)

    # print(response)
    response = response.replace("!", ".")

    # response = sub(response)

    response = remove_continuation_of_previous_tweet(response)

    if len(response) < 1:
        return ""

    # # APPEND PUNCTUATION IF NECESSARY
    # response = append_punctuation(response)
    # # print(response)

    # # Mention the original poster
    # # 5 in 6 chance
    # # # Unless this is a coaching channel
    # # if not active_channel == current_user.username:
    # response = mention(nick, response)

    return response


def is_bad(test_tweet):
    if b := next((b for b in bads if b in test_tweet.lower()), None):
        print("bad tweet: ", b, test_tweet)

    return 


def remove_continuation_of_previous_tweet(reply):
    """ in some cases openai will continue the previous tweet. This function removes that. """
    
    if "\n" not in reply:
        # print("no newline in reply")
        return reply

    elems = reply.split("\n")
    # elem0 = elems[0]
    # if not elem0.startswith(" - ") and not elem0.startswith(".") and len(elem0) >= 11:
    #     # print("elem0 doesn't start with - or . and it's length is greater than 11 so this must be a new tweet rather than a continuation of a response")
    #     return reply
    # print(f"deleting: {elems[0]}")
    # 

    """ assuming the actual response has no newlines """
    bad = "\n".join(elems[:-1])
    print(f"deleting: <{bad}>")
    return reply.replace(bad, "")


def get_twitter_vi():
    TWITTER_APP_KEY = os.environ.get("TWITTER_APP_KEY")
    TWITTER_APP_SECRET = os.environ.get("TWITTER_APP_SECRET")

    # TWITTER_v1
    TWITTER_OAUTH_TOKEN = os.environ.get("TWITTER_OAUTH_TOKEN")
    TWITTER_OAUTH_TOKEN_SECRET = os.environ.get("TWITTER_OAUTH_TOKEN_SECRET")

    auth = tweepy.OAuthHandler(TWITTER_APP_KEY, TWITTER_APP_SECRET)
    auth.set_access_token(TWITTER_OAUTH_TOKEN, TWITTER_OAUTH_TOKEN_SECRET)
    twitter_v1 = tweepy.API(auth, wait_on_rate_limit=True)
    return twitter_v1


def fetch_timeline_tweets(twitter_v1):
    """ Fetches the most popular 50 among the last 800 tweets from the home timeline"""
    timeline_tweets = []
    # https://docs.tweepy.org/en/stable/v1_pagination.html
    # for page in tweepy.Cursor(twitter_v1.home_timeline, tweet_mode="extended",  exclude_replies=True, include_entities=False, count=800).pages(4):
    #     for tweet in page:
    #         json = tweet._json
    #         timeline_tweets.append(json)
    timeline_tweets = twitter_v1.home_timeline(tweet_mode="extended",  exclude_replies=True, include_entities=False, count=200)    
    max_id = timeline_tweets[-1].id
    print(max_id)
    for i in range(4):
        timeline_tweets += twitter_v1.home_timeline(tweet_mode="extended",  exclude_replies=True, include_entities=False, count=200, max_id=max_id)
        max_id = timeline_tweets[-1].id
        print(i, max_id, len(timeline_tweets))

    
    print(len(timeline_tweets))
    return timeline_tweets


def twitter_routine(mode=mode):  # sourcery skip: raise-specific-error

    twitter_v1 = get_twitter_vi()

    # t  = get_full_text(1627275021961011201, twitter_v1)
    # print(t)
    # exit()



    # get the list of previous tweets from the text file
    with open("social/tweet_ids.txt", "r") as f:
        previous_tweets = f.read().splitlines()    

    # get the list of previous tweets from the text file
    with open("social/bad_users.txt", "r") as f:
        bad_users = f.read().splitlines() 
    print("bad_users", bad_users)


    # timeline = twitter_v1.home_timeline( )

    # for status in tweepy.Cursor(twitter_v1.home_timeline, "Tweepy",
    #     count=200).items():
    #     print(status.id)

    # timeline_tweets 
    # # timeline_tweets = fetch_timeline_tweets(twitter_v1)
    # print(f"timeline_tweets: {len(timeline_tweets)}")


    if mode == "twittermentions":
        tweets = twitter_v1.mentions_timeline(tweet_mode="extended", count=200 )
        tweets.sort(key=lambda x: x.user.followers_count, reverse=True)

    elif mode == "twittertimeline":
        tweets = test_tweets.test_tweets if test else fetch_timeline_tweets(twitter_v1)
        tweets.sort(key=lambda x: x.retweet_count + x.favorite_count, reverse=True)

    else:
        raise Exception("invalid mode")

    
    tweets = [x for x in tweets if x.id_str not in previous_tweets]
    tweets = [x for x in tweets if not is_bad(x.full_text) ]
    tweets = [x for x in tweets if x.favorite_count!=0 ]
    tweets = [x for x in tweets if str(x.user.id) not in bad_users ]
    


    for i, tweet in enumerate(tweets, start=1):
        # print(tweet)

        # id = tweet.id
        # if id in previous_tweets:
        #     continue
        text = tweet.full_text.replace("\n", " ") 
        # if is_bad(text):
        #     continue

        retweet_count = tweet.retweet_count
        favorite_count = tweet.favorite_count
        # if retweet_count > 150 or favorite_count > 150:
        screen_name = tweet.user.screen_name
        user_id = tweet.user.id
        followers_count = tweet.user.followers_count
        following_count = tweet.user.friends_count
        followers_minus_following = followers_count - following_count
        possibly_sensitive = tweet.possibly_sensitive if hasattr(tweet, "possibly_sensitive") else False
        log = f"{i}: {screen_name} | {text} | (retweets: {retweet_count}, favorites: {favorite_count}, followers: {followers_minus_following}, user_id: {user_id}"
        if possibly_sensitive:
            log += " (possibly sensitive)!!!"
        print(log)
                # print(json)


    # for i, tweet in enumerate(mentions , start=1):

        # if str(tweet.id) in previous_tweets:
        #     continue

        # text = tweet.text

        # if is_bad(text):

            # continue

        username = tweet.user.screen_name

        # print(f"{i}: <@{username}> '{text}'")

        test_message, language = get_test_message_and_language(text)

        reply = None

        prompt = random.choice(twitter_prompts)

        # every 4 items, add any additional context to the prompt
        if i % 4 == 0:
            prompt += f" Your response could mention the fact that {context}" 
            # print(prompt)

        reply = build_openai_response(text, prompt)   
        reply = finalize_response(reply, language)
        # reply = "test"
        reply = f"@{username} {reply}"
        if len(reply) > 280:
            # print(f"reply too long: {len(reply)}")
            reply = reply[:280]
            continue
        print(f"'{reply}'")
        print("\n")

        if not test:

            # ask for approval
            i = input("approve? (y)es / (n)o / i(gnore this tweet always)) ").lower()

            if i == "y":

                # post the reply to twitter
                twitter_v1.update_status(reply, in_reply_to_status_id =tweet.id)
                tweet.favorite()

            if i in ["i", "y"]:

                print('opening tweet_ids to save the id of the tweet')

                # save the ids of the tweet to a text file
                with open("social/tweet_ids.txt", "a") as f:
                    # print(f"writing {tweet.id} to tweet_ids.txt")

                    f.write(str(tweet.id) + "\n")

            elif i == 'q':
                exit()

            elif i == "tt":
                twitter_routine(mode="twittertimeline")



def main():
    print(mode)

    if mode in ["twittermentions", "twittertimeline"]:
        twitter_routine()
    elif mode == "reddit":
        reddit_routine()
    elif mode == "insta":
        insta_routine()



if __name__ == "__main__":
    main()

# def get_full_text(id, twitter_v1):  
#     """ get the full text of a tweet that has been truncated for length """

#     # get the full text of the tweet
#     tweet = twitter_v1.get_status(id, tweet_mode="extended")
#     text = tweet.full_text

#     # # remove the url
#     # text = text.split("https://")[0]

#     # # remove the username
#     # text = text.split("@")[0]

#     # # remove the hashtag
#     # text = text.split("#")[0]

#     # # remove the newline
#     # text = text.replace("\n", "")

#     return text