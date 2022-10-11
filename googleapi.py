import os
import pickle
import base64
import googlemaps
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.http import  (MediaIoBaseDownload,
                                   MediaFileUpload)


GTOKEN_FILE = os.environ['PACBONEXP_GTOKENFILE']

from utils import listsum

def get_service(service_name, version):
    with open(GTOKEN_FILE, 'rb') as token:
        creds = pickle.load(token)
    service = build(service_name,
                    version,
                    credentials=creds)
    return service


def get_gmail_service():
    return get_service('gmail', 'v1')


def get_gdrive_service():
    return get_service('drive', 'v3')


def get_file_items(service=None, pagesize=500):
    if service is None:
        service = get_gdrive_service()
    finished = False
    while not finished:
        items = []
        npg = None
        pg = 1
        while True:
            logger.info('Getting page %d of gdrive filelist' % pg)
            if npg:
                results = service.files().list(pageSize=pagesize,
                                               pageToken=npg,
                        fields="nextPageToken, files(id, name)").execute()
            else:
    	        results = service.files().list(pageSize=pagesize,
        		fields="nextPageToken, files(id, name)").execute()
            pg += 1
            if 'files' in results:
                new_items = results.get('files')
                items += new_items
            else:
                break
            if 'nextPageToken' in results:
                npg = results['nextPageToken']
            else:
                finished = True
                break
    return items


def get_file_id_from_name(name, service=None, pagesize=500):
    items = get_file_items(service=service, pagesize=pagesize)
    for item in items:
        if item['name'] == name:
            return item['id']


def download_csv_file(path, file_id=None, name=None, service=None, mimeType='text/csv'):
    if service is None:
        service = get_gdrive_service()
    if file_id is None:
        assert name is not None, name
        file_id = get_file_id_from_name(name, service=service)

    if file_id is None:
        logger.debug("file %s not found" % name)
        
    request = service.files().export(fileId=file_id,
                                     mimeType=mimeType)
    with open(path, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        logger.info("Download %s %d%%." % (path, int(status.progress() * 100)))


def get_csv_file(filename):
    path = os.path.join(CODE_DIR, filename + '.csv')
    download_csv_file(path, name=filename)
    return pd.read_csv(path, keep_default_na = False)
                        
        
def upload_csv_file(path, name, service=None):
    if service is None:
        service = get_gdrive_service()    
    file_metadata = {'name': name,
                     'mimeType': 'application/vnd.google-apps.spreadsheet'}
    media = MediaFileUpload(path,
                            mimetype='text/csv',
                            resumable=True)
    file = service.files().create(body=file_metadata,
                                    media_body=media,
                                    fields='id').execute()
    return file.get('id')


def convert_to_pdf(df,
                   name,
                   csvpath,
                   pdfpath,
                   formatting_requests=None,
                   header=None):
    df.to_csv(csvpath, index=False , encoding = 'utf-8')
    if header:
        csvstr = open(csvpath, 'r').read()
        csvstr = header + '\n' + csvstr
        with open(csvpath, 'w') as _f:
            _f.write(csvstr)
    file_service = get_gdrive_service()
    sheet_service = get_service("sheets", "v4")
    upload_csv_file(csvpath, name, service=file_service)
    if formatting_requests:
        sheet_id = get_sheet_id(name=name,
                                file_service=file_service,
                                sheet_service=sheet_service)
        for req in formatting_requests:
            for reqtype in req:
                reqval = req[reqtype]
                if "range" in reqval:
                    reqval["range"]["sheet_id"] = sheet_id
        spreadsheet_action('batchUpdate',
                           formatting_requests,
                           name=name,
                           body_type='requests',
                           get_values=False,
                           file_service=file_service,
                           sheet_service=sheet_service)
    download_csv_file(pdfpath, name=name, mimeType='application/pdf')


def get_sheet_id(file_id=None, name=None, file_service=None, sheet_service=None, sheet_num=0):
    if sheet_service is None:
        sheet_service = get_service("sheets", "v4")
    if file_id is None:
        file_id = get_file_id_from_name(name, service=file_service)
    sheetObj = sheet_service.spreadsheets().get(spreadsheetId=file_id,
                                                fields='sheets(properties(sheetId,title))').execute()
    sheet_id = sheetObj['sheets'][sheet_num]['properties']['sheetId']
    return sheet_id

    
def spreadsheet_action(aname,
                       data,
                       file_id=None,
                       name=None,
                       sheet_service=None,
                       file_service=None,
                       valueInputOption='RAW',
                       body_type='values',
                       get_values=True,
                       **kwargs):
    
    if sheet_service is None:
        sheet_service = get_service('sheets', 'v4')

    if file_id is None:
        assert name is not None, name
        file_id = get_file_id_from_name(name, service=file_service)

    body = {body_type: data}

    resource = sheet_service.spreadsheets()

    if get_values:
        resource = resource.values()
        kwargs['valueInputOption'] = valueInputOption

    func = getattr(resource, aname)
    
    resp = func(spreadsheetId=file_id,
                body=body,
                **kwargs).execute()

    return resp


