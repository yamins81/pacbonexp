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



@app.route('/create_test_bestinshow', methods=["GET", "POST"])
def get_test_bestinshow_from_gdrive():
    test_bis_path = os.path.join(CODE_DIR, 'pacbonexp_test_bestinshow.csv')
    googleapi.download_csv_file(test_bis_path,
                                name='pacbonexp_test_bestinshow')
    df = pd.read_csv(test_bis_path).fillna('')
    outcomes = get_bestinshow_from_data(df)
    bis_ranking = outcomes['ranking']

    bis_rankname = 'pacbonexp_test_bestinshow_ranks'
    bis_ranking_path = os.path.join(CODE_DIR, bis_rankname + '.csv')

    rid = googleapi.get_file_id_from_name(bis_rankname)
    if rid is None:
        print("Target file doesn't exist, making")
        bis_ranking.to_csv(bis_ranking_path, index=False, encoding='utf-8')
        googleapi.upload_csv_file(bis_ranking_path, bis_rankname)

    else:
        print("Target file already exists, updating")
        bis_ranking_recs = [list(bis_ranking.columns)] + [list(n) for i, n in bis_ranking.iterrows()]

        googleapi.spreadsheet_action('clear',
                                     None,
                                     name=bis_rankname,
                                     valueInputOption=None,
                                     body_type=None,
                                     range=bis_rankname)
        googleapi.spreadsheet_action('update',
                                     bis_ranking_recs,
                                     name=bis_rankname,
                                     range='A1')
        googleapi.download_csv_file(bis_ranking_path, name=bis_rankname)

    
    return 'success'


def level_to_points(level):
    if level == 1:
        return 5
    elif level == 2:
        return 3
    elif level == 3:
        return 1


def get_bestinshow_from_data(df):
    votes = {}
    for i, rec in df.iterrows():
        for j in range(1, 4):
            choice = rec['%d_choice' % j]
            if choice not in votes:
                votes[choice] = {}
            if j not in votes[choice]:
                votes[choice][j] = 0
            votes[choice][j] += 1

    new_recs = []
    for choice in votes:
        vrec = votes[choice]
        pts = sum([vrec[j] * level_to_points(j) for j in  vrec])
        new_rec = {}
        new_rec['display']= choice
        for j in vrec:
            new_rec['%d_votes' % j] = vrec[j]
        new_rec['points'] = pts
        new_recs.append(new_rec)
        
    new_df = pd.DataFrame(new_recs).fillna(0)
    new_df = new_df.sort_values(by='points', ascending=False)
    vcols = [k for k in new_df.columns if 'votes' in k]
    vcols.sort()
    cols = ['display'] + vcols + ['points']
    new_df = new_df[cols]

    return {'ranking': new_df}
    

@app.route('/create_test_rankings', methods=["GET", "POST"])
def get_test_rankings_from_gdrive():
    test_score_path = os.path.join(CODE_DIR, 'pacbonexp_test_scores.csv')
    googleapi.download_csv_file(test_score_path,
                                name='pacbonexp_test_scores')
    df = pd.read_csv(test_score_path)
    outcomes = get_rankings_from_data(df)
    rankings = outcomes['rankings'].fillna('')
    winners = outcomes['winners'].fillna('')
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

        googleapi.spreadsheet_action('clear',
                                     None,
                                     name=rankname,
                                     valueInputOption=None,
                                     body_type=None,
                                     range=rankname)
                                     
        googleapi.spreadsheet_action('update',
                                     ranking_recs,
                                     name=rankname,
                                     range='A1')

        googleapi.spreadsheet_action('clear',
                                     None,
                                     name=winnername,
                                     valueInputOption=None,
                                     body_type=None,
                                     range=winnername)
        googleapi.spreadsheet_action('update',
                                     winners_recs,
                                     name=winnername,
                                     range='A1')

        googleapi.download_csv_file(rankings_path, name=rankname)
        googleapi.download_csv_file(winners_path, name=winnername)
    
    return 'success'

    
def get_rankings_from_data(df):
    judge_cols = [k for k in df.columns if 'judge_' in k]
    zscored = {k: stats.mstats.zscore(df[k].fillna(0)) for k in judge_cols}
    for k in judge_cols:
        df['%s_zscored' % k] = zscored[k]
    avg_zscores = [np.mean([df[['%s_zscored' % k]].iloc[i]  for k in judge_cols]) for i in range(len(df))]

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
