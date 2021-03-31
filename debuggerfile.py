# -*- coding: utf-8 -*-
"""
Created on Tue Mar 30 13:17:55 2021

@author: aksbr
"""
import os, sys
from flask import Flask, request, make_response
import json
import pandas as pd
import numpy as np
import random
import datetime
from dateutil.relativedelta import relativedelta


user_df = pd.read_csv("C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/user.csv")
disease_df = pd.read_csv("C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/disease.csv")
userclaim_df = pd.read_csv("C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/userclaim.csv")
userprod_df = pd.read_csv("C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/userprod.csv")
prod_df = pd.read_csv("C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/prod.csv")
prodcov_df = pd.read_csv("C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/prodcov.csv")

def user_response(uid):
    user_df = pd.read_csv("C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/user.csv")
    row = user_df.loc[user_df.id == int(uid), 'name']
    if len(row) != 0:
        fulfillmentText = 'Welcome {}! How may I help you today? You can querry about your premiums or claims or you can also ask me about product recommendations!'.format(row.values[0])
    else :
        fulfillmentText = 'Your ID is not there in our database! Please re-enter your ID.'
        
    return {
        "fulfillmentText": fulfillmentText
        }

def get_service_response(user_id,disease):
    
    dfd = pd.read_csv('C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/disease.csv')
    dfc = pd.read_csv('C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/userclaim.csv')
    dfc = pd.merge(dfc, dfd, left_on='did', right_on='id').drop('id', axis=1)
    dfpc = pd.read_csv('C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/prodcov.csv')
    dfpc = pd.merge(dfpc, dfd, left_on='did', right_on='id').drop('id', axis=1)
    dfup = pd.read_csv('C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/userprod.csv')
    dfupc = pd.merge(dfup, dfpc, left_on='pid', right_on='pid')
    df = pd.merge(dfc, dfupc, left_on=['uid','pid','did','name'], right_on=['uid','pid', 'did','name'], how='outer').fillna('$0')
    row = df.loc[(df.uid == id) & (df.name == disease.lower()),['pid', 'amt', 'maxamt']]
    # print(row)
    fulfillmentText = ''
    if len(row) > 0:
        for i in range(len(row)):
            fulfillmentText += 'Your coverage for {} for the product {} is {} and you have claimed {} of {}. '.format(disease, row.values[i][0], row.values[i][2], row.values[i][1], row.values[i][2])
    else:
        fulfillmentText = '{} is not covered in your policy'.format(disease)

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

cbf_repo = pd.read_csv('C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/cbf_reco.csv')


def get_cbf_recommendation(pid): # in case of existing user feturn top 5 recommended products based on what he has bought
    df = pd.read_csv('C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/cbf_reco.csv')
    dfp = pd.read_csv('C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/prod.csv')
    pids = df[df.Product == pid].values.tolist()[0][2:]
    return dfp.loc[dfp.id.isin(pids), 'pname'].values.tolist()

def get_recommend_response(user_id):
    df = pd.read_csv("C:/Users/aksbr/Desktop/TCS/Officework/Insurance messenger/userprod.csv")
    pid = random.choice(df.loc[(df.uid == user_id), 'pid'].tolist())
    pnames = get_cbf_recommendation(pid)
    fulfillmentText = 'Top 2 products recommended for you are the following: {} .'.format(', '.join(map(str, pnames)))
    return {
    "fulfillmentText": fulfillmentText
    }

