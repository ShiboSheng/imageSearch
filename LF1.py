import json
import urllib.parse
import boto3
import requests
from datetime import datetime
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

opensearch_host = "search-photos-5jcv3q4icmnpfuq7mfjo6v36q4.us-east-1.es.amazonaws.com"
region = "us-east-1"

def build_search_client(host, port=443):
    service = "es"
    credentials = boto3.Session().get_credentials()
    awsauth = AWS4Auth('AKIAQQ3LP4USU43VTMHR', '29fBf/Fg4ddotmlQPqI99BM+1ueL4rwQOqzcFjzL', region, service, None)

    client = OpenSearch(
        hosts=[{'host': host, 'port': port}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )
    return client

print('Loading function')

s3 = boto3.client('s3')


def detect_labels(labels, bucket, key):
    client = boto3.client('rekognition')
    response = client.detect_labels(
        Image={
            'S3Object': {
                'Bucket': bucket,
                'Name': key,
            }
        },
        MaxLabels=10,
        MinConfidence=90
    )
    for label in response['Labels']:
        labels.append(label['Name'])
    return labels
    

def get_metadata(client, bucket, key):
    response = client.head_object(Bucket=bucket, Key=key)
    try:
        custom_labels = response["Metadata"]["customlabels"]
        labels = custom_labels.split(",")
    except KeyError:
        labels = []
    return labels


def send_opensearch(bucket, key, labels):
    opensearch = build_search_client(opensearch_host)
    document = {
        'objectKey': key,
        'bucket': bucket,
        'createdTimestamp': datetime.now().strftime("%m/%d/%Y, %H:%M:%S"),
        'labels': ','.join(labels)
    }
    opensearch.index(
        index="photoalbum",
        body=document,
        refresh=True
    )
    


def lambda_handler(event, context):
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    custom_labels = get_metadata(s3, bucket, key)
    full_labels = detect_labels(custom_labels, bucket, key)
    print(full_labels)
    send_opensearch(bucket, key, full_labels)
    return {
        'statusCode': 200,
        'body': json.dumps('Info uploaded to OpenSearch.')
    }    


    
    

