import json
from sys import getsizeof
import re
import math
import collections, functools, operator 
from datetime import datetime
import boto3
import uuid
import os
from contextlib import closing

#Client to access S3 service
s3_client = boto3.client('s3', region_name = 'us-east-1')
s3 = boto3.resource('s3', region_name = 'us-east-1')

#Creating S3 buckets and folders for input and output results
bucket1 = "inputbucketsentiment"
bucket2 = "outputbucketsentiment"
bucket3 = "audiofrompost"

#Creating input and output buckets to store user inputs and comprehend results
s3.create_bucket(Bucket=bucket1)
s3.create_bucket(Bucket=bucket2)

#Timestamps to give keynames for objects we push to S3
now = datetime.now()
current_time = now.strftime("%H:%M:%S")

#For translate client
translate = boto3.client(service_name='translate', region_name='us-east-1', use_ssl=True)

# for comprehend client
client = boto3.client('comprehend')

# for dynamodb
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('post')

def lambda_handler(event, context):
    
    #User input
    res = event['text']
    dest_lang = event['dest_lang']
    
    recordId = str(uuid.uuid4())
    voice = event['voice']
    #print(res)
    
    source_lang=json.dumps(client.detect_dominant_language(Text = res), sort_keys=True, indent=4)
    
    languageCode=source_lang.split("\n")[3]
    
    lang = str()
    cn = 0
    for i in range(len(languageCode)):
        if(languageCode[i] == '\"'):
            cn += 1
        if cn == 3:
            lang += languageCode[i]
        elif cn == 4:
            break
    source_lang=lang[1:]
    
    result=translate.translate_text(Text=res, SourceLanguageCode=source_lang, TargetLanguageCode=dest_lang)
    
    translatedText=result.get("TranslatedText")
    
    #Storing user input in S3 input bucket
    s3_client.put_object(Body = res, Bucket = bucket1, Key = current_time + ".txt")
    
    #Inputs less than 5000 bytes can use normal detect sentiment call 
    if comprehendCall(translatedText):
        print("This is less than 5000 bytes, going to use normal detect sentiment call")
        print(getsizeof(translatedText))
        sentiment = client.detect_sentiment(Text = translatedText, LanguageCode = dest_lang)
        sentRes = sentiment['Sentiment']
        sentScore = sentiment['SentimentScore']
        
    #otherwise use batch detect sentiment call
    else:
        print("Using the Batch Detect Sentiment Call")
        #print(getsizeof(translatedText))
        inputSentList = tokenizeText(translatedText)
        sentResults = client.batch_detect_sentiment(TextList = inputSentList, LanguageCode = dest_lang) #returns a dictionary with value as list of dictionaries
        #print(sentResults)
        sentResults = sentResults['ResultList'] #list of dictionaries 
        sentScores = [sentResult['SentimentScore'] for sentResult in sentResults] #Accessing scores for each of four categories
        numSent = len(sentScores) #Number of batches given to batch detect call
        sentScore = dict(functools.reduce(operator.add, map(collections.Counter, sentScores))) # sum the values with same keys
        sentScore = {key: (sentScore[key]/numSent) for key in sentScore.keys()}
        print(sentScore)
    
    #Storing Comprehend output   
    s3_client.put_object(Body = str(sentScore), Bucket = bucket2, Key = current_time + ".txt")
    
    # Using polly to convert text to speech
    
    # Because single invocation of the polly synthesize_speech api can 
    # transform text with about 1,500 characters, we are dividing the 
    # post into blocks of approximately 1,000 characters.
    textBlocks = []
    while (len(translatedText) > 1100):
        begin = 0
        end = translatedText.find(".", 1000)

        if (end == -1):
            end = translatedText.find(" ", 1000)
            
        textBlock = translatedText[begin:end]
        translatedText = translatedText[end:]
        textBlocks.append(textBlock)
    textBlocks.append(translatedText)            

    #For each block, invoke Polly API, which will transform text into audio
    polly = boto3.client('polly')
    for textBlock in textBlocks: 
        response = polly.synthesize_speech(
            OutputFormat='mp3',
            Text = textBlock,
            VoiceId = voice
        )
        
        #Save the audio stream returned by Amazon Polly on Lambda's temp 
        # directory. If there are multiple text blocks, the audio stream
        # will be combined into a single file.
        if "AudioStream" in response:
            with closing(response["AudioStream"]) as stream:
                output = os.path.join("/tmp/", recordId)
                with open(output, "ab") as file:
                    file.write(stream.read())



    s3_client.upload_file('/tmp/' + recordId, 
      bucket3, 
      recordId + ".mp3")
    s3_client.put_object_acl(ACL='public-read', 
      Bucket=bucket3, 
      Key= recordId + ".mp3")

    location = s3_client.get_bucket_location(Bucket=bucket3)
    region = location['LocationConstraint']
    
    if region is None:
        url_begining = "https://s3.amazonaws.com/"
    else:
        url_begining = "https://s3-" + str(region) + ".amazonaws.com/" \
    
    url = url_begining \
            + str(bucket3) \
            + "/" \
            + str(recordId) \
            + ".mp3"
            
    # put item to table
    table.put_item(
        Item={
            'id' : recordId,
            'text' : translatedText,
            'voice' : voice,
            'url' : url
        }
    )
    
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
        },
        'body': sentScore,
        'translated_text': translatedText,
        'url_post': url,
    }

def comprehendCall(sampStr):
    """Determines which Comprehend call to use"""
    sizeStr = getsizeof(sampStr)
    if sizeStr < 5000:
        return True
    return False

def countSplits(sampStr):
    """Number of times we need to split input string for batch sentiment call"""
    sizeStr = getsizeof(sampStr)
    if sizeStr > 5000:
        numSplits = math.ceil(sizeStr/5000)
        if numSplits > 25:
            raise("This text is too large for analysis try something else")
    return numSplits

def tokenizeText(sampStr):
    """Tokenizing text into sentences to make sure data is split properly"""
    sentList = re.split(r'(?<=[^A-Z].[.?]) +(?=[A-Z])', sampStr)
    numSentences = len(sentList)
    numSplits = countSplits(sampStr)
    
    #Storing size of each sentence to check if over 5000 limit
    sizesStr = []
    for sent in sentList:
        sizesStr.append(getsizeof(sent))
        for size in sizesStr:
            if size > 5000:
                raise("This piece is too large for analysis")
            continue
    #print(sizesStr)
    if numSentences > 25:
        raise("Too many pieces for Comprehend to process, split text even more")
        #Combines two sentences into one list item
        sentList = [sentList[i] + sentList[i+1] if not numSentences %2 else 'odd index' for i in range(0,len(sentList),2)]
    return sentList