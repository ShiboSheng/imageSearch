import json
import boto3
import logging
import requests
from datetime import datetime
from opensearchpy import OpenSearch, RequestsHttpConnection
from aws_requests_auth.aws_auth import AWSRequestsAuth

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

opensearch_host = "search-photos-5jcv3q4icmnpfuq7mfjo6v36q4.us-east-1.es.amazonaws.com"
region = 'us-east-1'

def extract_label(input):
    lexv2 = boto3.client('lexv2-runtime')
    response = lexv2.recognize_text(
        botId='S9FEFDFCCC',
        botAliasId='TSTALIASID',
        localeId='en_US',
        sessionId='test_session',
        text=input
    )
    for message in response['messages']:
        logger.info(message['content'])
    labels = []
    slots = response['sessionState']['intent']['slots']
    for slot in slots:
        if slots[slot]:
            labels.append(slots[slot]['value']['interpretedValue'])
    logger.info("Extracted labels: " + str(labels))
    return labels


def build_search_client(host, port=443):
    credentials = boto3.Session().get_credentials()
    service = "es"
    awsauth = AWSRequestsAuth(
        aws_access_key=credentials.access_key,
        aws_secret_access_key=credentials.secret_key,
        aws_token=credentials.token,
        aws_host=opensearch_host,
        aws_region=region,
        aws_service=service
    )
    client = OpenSearch(
        hosts=[{'host': host, 'port': port}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )
    return client
    

def search_label(client, labels):
    search_label = labels[0]
    for label in labels[1:]:
        search_label += (" OR " + label)
    logger.info('Searching for ' + search_label)
    
    query = {
        "query": {
            "match": {
                "labels": {
                    "query": search_label,
                    "fuzziness": 'AUTO'
                }
            }
        }
    }
    opensearch_rsp = client.search(body=query, index='photoalbum')
    try:
        photos = opensearch_rsp['hits']['hits']
    except KeyError:
        return {'results': []}

    print(photos)
    results = []
    for photo in photos:
        photo = photo['_source']
        temp_dict = {}
        temp_dict['url'] = 'https://shibohw2b2.s3.amazonaws.com/' + photo['objectKey']
        temp_dict['labels'] = photo['labels']
        results.append(temp_dict)

    return {'results': results}


def lambda_handler(event, context):
    if event['queryStringParameters']:
        print("Input: " + event['queryStringParameters']['q'])
        labels = extract_label(event['queryStringParameters']['q'])
        print(labels)
        client = build_search_client(opensearch_host)
        results = search_label(client, labels)
        print(results)
        results = json.dumps(results)
        logger.info("Search result: " + results)
    else:
        body = "Please provide at least a label"
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Headers': '*',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,GET'
        },
        'body': results
    }
