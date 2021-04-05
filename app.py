# -*- coding: utf-8 -*-
"""
Created on Sun Mar  7 09:21:48 2021

@author: Akash Gupta, Sandipan Dey
"""

import os, sys
from flask import Flask, request, make_response
import json
import pandas as pd
import numpy as np
import random
import datetime
from dateutil.relativedelta import relativedelta



app = Flask(__name__)

session = {}

@app.route('/webhook',methods = ['POST'])

def results():
    global session
    # build a request object
    req = request.get_json(force=True)
    result = req.get('queryResult')
    parameters = result.get('parameters')
    intent = result.get('intent')['displayName']
    # print(session)
    user_id = parameters['user_id'] if "user_id" in parameters else session['user_id']
    # if not 'user_id' in session:
    if 'user_id' in parameters:
        session['user_id'] = user_id

    print(intent)
    print(parameters)
    print(user_id)
    if intent == 'userid':
        return user_response(user_id)
    if intent == 'askpremium':
        prod_id = parameters['prod_id']
        return  ask_premium_response(user_id,prod_id)
    if intent == 'askclaim':
        disease = parameters['disease']
        return get_service_response(user_id,disease)
    if intent == 'askrecommendation':
        return get_recommend_response(user_id)


# create a route for webhook
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # return response
    return make_response(jsonify(results()))




def user_response(uid):
    user_df = pd.read_csv("C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/user.csv")
    row = user_df.loc[user_df.id == int(uid), 'name']
    if len(row) != 0:
        fulfillmentText = 'Hey {}! How are you?'.format(row.values[0])
    else :
        fulfillmentText = 'Couldnt find your ID. Please check & enter again.'
        
    return {
        "fulfillmentText": fulfillmentText
        }
    

def get_service_response(user_id,disease):
    
    user_df = pd.read_csv("C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/user.csv")
    user_name = user_df.loc[user_df.id == int(user_id), 'name'].values[0]
    dfd = pd.read_csv('C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/disease.csv')
    dfc = pd.read_csv('C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/userclaim.csv')
    dfc = pd.merge(dfc, dfd, left_on='did', right_on='id').drop('id', axis=1)
    dfpc = pd.read_csv('C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/prodcov.csv')
    dfpc = pd.merge(dfpc, dfd, left_on='did', right_on='id').drop('id', axis=1)
    dfup = pd.read_csv('C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/userprod.csv')
    dfupc = pd.merge(dfup, dfpc, left_on='pid', right_on='pid')
    df = pd.merge(dfc, dfupc, left_on=['uid','pid','did','name'], right_on=['uid','pid', 'did','name'], how='outer').fillna('$0')
    row = df.loc[(df.uid == user_id) & (df.name == disease.lower()),['pid', 'amt', 'maxamt']]
    # print(row)
    fulfillmentText = ''
    if len(row) > 0:
        for i in range(len(row)):
            fulfillmentText += 'Your coverage for {} under Policy ID {}\nTotal claims= {}\nAlreday claimed = {}. \n'.format(disease, row.values[i][0], row.values[i][2], row.values[i][1])
    else:
        fulfillmentText = '{}! Sorry but {} is not covered in your policy'.format(user_name,disease)

    return {
    "fulfillmentText": fulfillmentText
    }

#Premium helper function for both ask_premium & alert_premium   
def get_premium_info(uid, pid):

    user_df = pd.read_csv("C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/user.csv")
    userprod_df = pd.read_csv("C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/userprod.csv")
    prod_df = pd.read_csv("C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/prod.csv")
    userprod_df['date'] = pd.to_datetime(userprod_df['date'])
    
    prem_count = userprod_df.loc[(userprod_df.uid == int(uid)) & (userprod_df.pid == int(pid)),'nprpaid'].values[0]
    prem_amt = prod_df.loc[prod_df.id == int(pid), 'pramt'].values[0]
    user_name = user_df.loc[user_df.id == int(uid), 'name'].values[0]                           
    pr_once = prod_df.loc[prod_df.id == int(pid), 'pronce'].values[0]
    start_date = userprod_df.loc[(userprod_df.uid == int(uid)) & (userprod_df.pid == int(pid)),'date'].values[0]
    npr_paid = userprod_df.loc[(userprod_df.uid == int(uid)) & (userprod_df.pid == int(pid)),'nprpaid'].values[0]

    return prem_count, prem_amt, user_name, pr_once, npr_paid, start_date



def ask_premium_response(uid,pid):
    
    
    prem_count, prem_amt, user_name, pr_once, npr_paid, start_date = get_premium_info(uid, pid)
    start_date = pd.Timestamp(start_date)
    due_date = start_date + relativedelta(years =1)
    today_date = datetime.datetime.now()
    real_paid = int((today_date - start_date).days/365)
    
    if pr_once == 'yes' and npr_paid == 0:
        fulfillmentText = 'Dear {}!'.format(user_name) + '\ntotal premium amount = {}!\nNot paid yet. Please Pay it ASAP'.format(prem_amt)
    elif pr_once == 'yes' and npr_paid == 1 :
        fulfillmentText = 'Dear {}!'.format(user_name) + '\ntotal premium amount = {}!\nPayment is done.Thanks!.'.format(prem_amt)
        
    elif pr_once == 'no':
        due_date = start_date + relativedelta(years = npr_paid)
        if npr_paid < real_paid:
            fulfillmentText = 'Dear {}!'.format(user_name) + '\ntotal premium amount = {}!'.format(prem_amt) + "\nPaid premiums = {}".format(npr_paid)+ "\nRemaining = {}\nPlease pay ASAP".format(real_paid-npr_paid)
        elif npr_paid == real_paid:
            fulfillmentText = 'Dear {}!'.format(user_name) + '\ntotal premium amount = {}!'.format(prem_amt)  +  "\nYou must pay it before {} ".format(due_date.strftime("%d")) + '{},'.format(due_date.strftime("%B")) + '{}'.format(due_date.strftime("%Y"))
    else:
        fulfillmentText = results().result.fulfillmentText 
    return {
        "fulfillmentText": fulfillmentText
        }

def preprocess_create_product_profile():
    df1 = pd.read_csv('C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/prodcov.csv')
    df2 = df1.groupby(['pid'])['maxamt'].agg([('maxamt',lambda x: int(x.str.replace('$','').astype(int).sum()))]).reset_index()
    #df2['maxamt'] = '$' + df2['maxamt'].astype(str)
    df = pd.read_csv('C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/prod.csv')
    df['pramt'] = df['pramt'].str.replace('$','').astype(int)
    df = pd.merge(df, df2, left_on='id', right_on='pid').drop('id', axis=1)
    df = df[['pid', 'pronce', 'pramt', 'maxamt', 'term_yrs', 'interest']]
    pids = df.pid
    df1 = pd.get_dummies(df[['pronce', 'interest']]) 
    df = pd.concat([df[['pramt','maxamt','term_yrs']], df1], axis=1)
    df = df.apply(lambda x: x / np.linalg.norm(x), axis=1)
    df = pd.concat([pids, df], axis=1)
    return df

def provide_cbf_recommendation(df, k=3):
    pids = df.pid.tolist()
    mat = df.drop('pid', axis=1).to_numpy()
    cosine_sim = mat @ mat.T
    rec1 = np.argsort(-cosine_sim, axis=1)[:,:k]
    rec1 = pd.DataFrame(data=np.array(pids)[rec1],    
                  index=pids,    
                  columns=['Recomm' + str(i+1) for i in range(k)])
    rec1['Product'] = pids
    rec1 = rec1[['Product'] + rec1.columns.values.tolist()[:-1]]
    return rec1

provide_cbf_recommendation(preprocess_create_product_profile()).to_csv('C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/cbf_reco.csv', index=False)

def get_cbf_recommendation(pid): # in case of existing user feturn top 5 recommended products based on what he has bought
    df = pd.read_csv('C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/cbf_reco.csv')
    dfp = pd.read_csv('C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/prod.csv')
    pids = df[df.Product == pid].values.tolist()[0][2:]
    return dfp.loc[dfp.id.isin(pids), 'pname'].values.tolist()

def get_recommend_response(uid):
    user_df = pd.read_csv("C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/user.csv")
    user_name = user_df.loc[user_df.id == int(uid), 'name'].values[0]
    df = pd.read_csv("C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/userprod.csv")
    pid = random.choice(df.loc[(df.uid == uid), 'pid'].tolist())
    pnames = get_cbf_recommendation(pid)
    fulfillmentText = '{},'.format(user_name)+ ' Top most recommended Policies for you are:\n{} .'.format(', '.join(map(str, pnames)))
    return {
    "fulfillmentText": fulfillmentText
    }

def get_a_random_recommendation(): # in case of new user
    df =  pd.read_csv('C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/prod.csv')
    pname = random.choice(df.pname.tolist())
    fulfillmentText = 'You can buy the product {}.'.format(pname)
    return {
        "fulfillmentText": fulfillmentText
        }
if __name__ == '__main__':
    app.run(debug = True, port = 8080)
    
    

    
