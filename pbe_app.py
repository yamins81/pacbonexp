import os
import hashlib
from functools import wraps
import pandas as pd
import numpy as np
import scipy.stats as stats

from flask import (Flask,
                   render_template)
from flask import request, Response
app = Flask(__name__)

from settings import *

import googleapi

userhash = 'a90e6e60079f5e07d02541384fa95a9aec31144ad3a5f4b46e22bc0c38623624'
passwdhash = '09ff6bdc2e8bce7fc2abc5a909fcf059a0a99ec7f9717ddba869d003bdf38e51'

def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    uname_enc = hashlib.sha256(bytes(username, encoding='utf-8')).hexdigest()
    pword_enc = hashlib.sha256(bytes(password, encoding='utf-8')).hexdigest()
    return uname_enc == userhash and pword_enc == passwdhash


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL. You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


@app.route('/pbe_rankings.html')
@requires_auth
def vis():
    return render_template('rankings.html')


@app.route('/ranking_data', methods=["GET", "POST"])
def get_rankings():
    df = pd.read_csv('test_scores.csv').fillna('')
    rankings = get_rankings_from_data(df)
    rankings['rankings'] = rankings['rankings'].to_html()
    rankings['winners'] = rankings['winners'].to_html()
    return rankings


@app.route('/create_test_rankings', methods=["GET", "POST"])
def get_test_rankings_from_gdrive():
    test_score_path = os.path.join(CODE_DIR, 'pacbonexp_test_scores.csv')
    googleapi.download_csv_file(test_score_path,
                                name='pacbonexp_test_scores')
    df = pd.read_csv(test_score_path).fillna('')
    outcomes = get_rankings_from_data(df)
    rankings = outcomes['rankings']
    winners = outcomes['winners']
    rankings_path = os.path.join(CODE_DIR, 'test_rankings.csv')
    winners_path = os.path.join(CODE_DIR, 'test_winners.csv')

    rankname = 'pacbonexp_test_rankings'
    winnername = 'pacbonexp_test_winners'

    rid = googleapi.get_file_id_from_name(rankname)
    wid = googleapi.get_file_id_from_name(winnername)
    if rid is None or wid is None:
        print("Target files don't exist, making")
        rankings.to_csv(rankings_path, index=False, encoding='utf-8')
        winners.to_csv(winners_path, index=False, encoding='utf-8')
        googleapi.upload_csv_file(rankings_path, rankname)
        googleapi.upload_csv_file(winners_path, winnername)

    else:
        print("Target files already exist, updating")
        ranking_recs = [list(rankings.columns)] + [list(n) for i, n in rankings.iterrows()]
        winners_recs = [list(winners.columns)] + [list(n) for i, n in winners.iterrows()]

        googleapi.spreadsheet_action('update',
                                     ranking_recs,
                                     name=rankname,
                                     range='A1')

        googleapi.spreadsheet_action('update',
                                     winners_recs,
                                     name=winnername,
                                     range='A1')

        googleapi.download_csv_file(rankings_path, name=rankname)
        googleapi.download_csv_file(winners_path, name=winnername)
    
    return 'success'

    
def get_rankings_from_data(df):
    zscored = [stats.mstats.zscore(df['judge_%d' % d]) for d in range(1, 8)]
    for d in range(1, 8):
        df['judge_%d_zscored' % d] = zscored[d - 1]
    avg_zscores = [np.mean([df[['judge_%d_zscored' % d]].iloc[i]  for d in range(1, 8)]) for i in range(len(df))]

    df['avg_zscore'] = avg_zscores

    overall_ranks = len(df) - np.argsort(avg_zscores).argsort()

    df['overall_rank'] = overall_ranks

    df['category_rank'] = np.zeros_like(df['overall_rank'])

    categories = np.unique(df['category'])

    for c in categories:
        iscat = df['category'] == c
        dfcat = df[iscat]
        cat_zscores = dfcat['avg_zscore']
        category_ranks = len(dfcat) - np.argsort(cat_zscores).argsort() 
        df.loc[iscat, 'category_rank'] = category_ranks

    category_winners = df[df['category_rank'] == 1]

    return {"rankings": df,
            "winners": category_winners}
    
if __name__ == "__main__":
    #app.run(ssl_context='adhoc')
    app.run(ssl_context=('cert.pem', 'key.pem'))
