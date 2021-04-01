"""
AWS lambda code for Voicebot
### authors: Akash Gupta, Sandipan Dey
# https://www.facebook.com/AIIAssitant-108792264632368
"""

import random
import json

#!pip install pandas

import pandas as pd
import datetime
from dateutil.relativedelta import relativedelta

# --------------- Helpers that build all of the responses ----------------------

def build_speechlet_response(title, output, reprompt_text, should_end_session):
    return {
        'outputSpeech': {
            'type': 'PlainText',
            'text': output
        },
        'card': {
            'type': 'Simple',
            'title': "SessionSpeechlet - " + title,
            'content': "SessionSpeechlet - " + output
        },
        'reprompt': {
            'outputSpeech': {
                'type': 'PlainText',
                'text': reprompt_text
            }
        },
        'shouldEndSession': should_end_session
    }

def build_response(session_attributes, speechlet_response):
    return {
        'version': '1.0',
        'sessionAttributes': session_attributes,
        'response': speechlet_response
    }

# ----- recommendation --------------------------
def preprocess_create_product_profile():
    df1 = pd.read_csv('prodcov.csv')
    df2 = df1.groupby(['pid'])['maxamt'].agg([('maxamt',lambda x: int(x.str.replace('$','').astype(int).sum()))]).reset_index()
    #df2['maxamt'] = '$' + df2['maxamt'].astype(str)
    df = pd.read_csv('prod.csv')
    df['pramt'] = df['pramt'].str.replace('$','').astype(int)
    df = pd.merge(df, df2, left_on='id', right_on='pid').drop('id', axis=1)
    df = df[['pid', 'pronce', 'pramt', 'maxamt', 'term_yrs', 'interest']]
    pids = df.pid
    df1 = pd.get_dummies(df[['pronce', 'interest']]) 
    df = pd.concat([df[['pramt','maxamt','term_yrs']], df1], axis=1)
    df = df.apply(lambda x: x / np.linalg.norm(x), axis=1)
    df = pd.concat([pids, df], axis=1)
    return df

def provide_cbf_recommendation(df, k=6):
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

# generate CBF recommendation
# df = preprocess_create_product_profile()
# rec = provide_cbf_recommendation(df)
# rec.head(20)
# rec.to_csv('alexa/voicebot/cbf_reco.csv', index=False)

# --------------- Functions that control the skill's behavior ------------------
def get_policy_expiry_alert(uid):
    dfp =  pd.read_csv('prod.csv')
    dfup = pd.read_csv('userprod.csv')
    df = pd.merge(dfp, dfup, left_on=['id'], right_on=['pid'], how='inner').drop('id', axis=1)
    df = df.loc[df.uid == uid]
    speech_output = ''
    if len(df) > 0:
        df['edate'] = pd.to_datetime(df['date'], errors='coerce') + pd.to_timedelta(df.term_yrs*365, unit='D')
        df['etime'] = df.edate - pd.Timestamp.now().normalize()
        for index, row in df.iterrows():
            et = row['etime'].days
            #print(et)
            if et < 0:
                speech_output += 'Your policy {} got already expired {} days back. '.format(row['pname'], abs(et))
            elif et < 30: # expiring in next 1 month
                speech_output += 'Your policy {} will expire in next {} days. '.format(row['pname'], et)
    #df.head()
    return speech_output

#Premium helper function for both ask_premium and alert_premium   
def get_premium_info(uid, pid):

    user_df = pd.read_csv("user.csv")
    userprod_df = pd.read_csv("userprod.csv")
    prod_df = pd.read_csv("prod.csv")
    userprod_df['date'] = pd.to_datetime(userprod_df['date'])
    
    prem_count = userprod_df.loc[(userprod_df.uid == int(uid)) & (userprod_df.pid == int(pid)),'nprpaid'].values[0]
    prem_amt = prod_df.loc[prod_df.id == int(pid), 'pramt'].values[0]
    user_name = user_df.loc[user_df.id == int(uid), 'name'].values[0]                           
    pr_once = prod_df.loc[prod_df.id == int(pid), 'pronce'].values[0]
    start_date = userprod_df.loc[(userprod_df.uid == int(uid)) & (userprod_df.pid == int(pid)),'date'].values[0]
    npr_paid = userprod_df.loc[(userprod_df.uid == int(uid)) & (userprod_df.pid == int(pid)),'nprpaid'].values[0]

    return prem_count, prem_amt, user_name, pr_once, npr_paid, start_date


def get_premium_alert(uid):
    
    df = pd.read_csv("userprod.csv")
    dfp = pd.read_csv('prod.csv')
    df = pd.merge(df, dfp, left_on=['pid'], right_on=['id']).drop('id', axis=1)
    res = df.loc[(df.uid == uid),['pid', 'pname']]
    speech_output = ''
    for _, row in res.iterrows():
        pid, pname = row['pid'], row['pname']
        prem_count, prem_amt, user_name, pr_once, npr_paid, start_date = get_premium_info(uid, pid)
        start_date = pd.Timestamp(start_date)
        today_date = datetime.datetime.now()
        prem_to_paid = (today_date - start_date).days/365   
        default_n = int(prem_to_paid) - npr_paid
        if pr_once == 'no':
            due_date = start_date + relativedelta(years = int(prem_to_paid))
            if default_n >= 2:
                speech_output += 'You have missed your last few premiums for the policy {} please pay them ASAP. '.format(pname)  
            elif default_n == 1:
                speech_output += 'Your last premium for policy {} was missed, which was due on {} of {} {}, please pay it ASAP. '.format(pname, due_date.strftime("%d"), due_date.strftime("%B"), due_date.strftime("%Y"))
        elif pr_once =='yes' and npr_paid == 0:
            speech_output += 'Your premium for policy {} is not yet paid! please pay it ASAP'.format(pname) 

    return speech_output

        
def get_id_response(intent, session):
    """ An example of a custom intent. Same structure as welcome message, just make sure to add this intent
    in your alexa skill in order for it to work.
    """
    print("SESSION BELOW")
    print(session)
    card_title = "Identify"
    df = pd.read_csv('user.csv')
    session_attributes = {}
    
    if 'value' in intent['slots']['id']:
        id = intent['slots']['id']['value']
        id = int(''.join(filter(str.isalnum, id)))
        #print(id)
        session_attributes = {'id': id}
        row = df.loc[df.id == int(id), 'name']
        speech_output = ''
        if len(row) != 0:
            speech_output = 'Welcome {}. '.format(row.values[0])
            alert = get_policy_expiry_alert(id)
            if alert:
                speech_output += alert #'Here are policy expiry alerts for you! ' + alert
            else:
                alert = get_premium_alert(id)
                #print(alert)
                if alert:
                    speech_output += alert #'Here are premium due alerts for you! ' + alert
            speech_output += '\n Now, tell me what do you want to know about? You can ask for your benefits, premiums and recommendations.'
        else:
            speech_output = 'Your ID is not there in my database! Please re-enter your ID. '
    else:
        speech_output = 'Please register to the system first and buy an insurance product! '
        speech_output += 'The recommended product for you is: {}'.format(get_a_random_recommendation())
    reprompt_text = "I said " + speech_output
        
    should_end_session = False
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))
        
def get_benefit_response(intent, session):
    """ An example of a custom intent. Same structure as welcome message, just make sure to add this intent
    in your alexa skill in order for it to work.
    """
    session_attributes = session.get('attributes', {})
    card_title = "Benefits"
    speech_output = 'what service do you want to know more about? you can ask for the coverage for a disease. '
    reprompt_text = "I said," + speech_output
    should_end_session = False
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))

def get_service_response(intent, session):
    """ An example of a custom intent. Same structure as welcome message, just make sure to add this intent
    in your alexa skill in order for it to work.
    """
    session_attributes = session.get('attributes', {})
    print("SESSION BELOW")
    print(session)
    card_title = "Service"
    disease = intent['slots']['disease']['value']
    #with open('test.json') as json_file:
    #    cov = json.load(json_file)['disease']
    session_attributes = session.get('attributes', {})
    id = int(session_attributes['id'])
    dfd = pd.read_csv('disease.csv')
    dfc = pd.read_csv('userclaim.csv')
    dfc = pd.merge(dfc, dfd, left_on='did', right_on='id').drop('id', axis=1)
    dfpc = pd.read_csv('prodcov.csv')
    dfpc = pd.merge(dfpc, dfd, left_on='did', right_on='id').drop('id', axis=1)
    dfp = pd.read_csv('prod.csv')
    dfup = pd.read_csv('userprod.csv')
    dfup = pd.merge(dfp, dfup, left_on='id', right_on='pid').drop('id', axis=1)
    dfupc = pd.merge(dfup, dfpc, left_on='pid', right_on='pid')
    df = pd.merge(dfc, dfupc, left_on=['uid','pid', 'did','name'], right_on=['uid','pid', 'did','name'], how='outer').fillna('$0')
    #df 
    row = df.loc[(df.uid == id) & (df.name == disease.lower()),['pname', 'amt', 'maxamt']]
    #print(row)
    speech_output = ''
    if len(row) > 0:
        for i in range(len(row)):
            speech_output += 'Your coverage for {} for the policy {} is {} and you have claimed {}. '.format(disease, row.values[i][0], row.values[i][2], row.values[i][1])
    else:
        speech_output = '{} is not covered in your policy'.format(disease)

    reprompt_text = "I said " + speech_output
        
    should_end_session = False
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))
        
def get_premium_response(intent, session):
    """ An example of a custom intent. Same structure as welcome message, just make sure to add this intent
    in your alexa skill in order for it to work.
    """
    print("SESSION BELOW")
    print(session)
    session_attributes = session.get('attributes', {})
    card_title = "Premium"
    df = pd.read_csv('userprod.csv')
    dfp = pd.read_csv('prod.csv')
    uid = int(session_attributes['id'])
    df = pd.merge(df, dfp, left_on='pid', right_on='id').drop('id', axis=1)
    #df.head()
    res = df.loc[(df.uid == uid),['pid','pname']]
    #res.pid.tolist()
    speech_output = ''
    if len(res) > 0:
        for _, row in res.iterrows():
            pid, pname = row['pid'], row['pname']
            #if len(df[(df.uid == uid) & (df.pid == pid)]) == 0:
            #    speech_output = 'The product id {} does not exist in your purchase history! re-enter your product id'.format(pid)
            #else:        
            prem_count, prem_amt, user_name, pr_once, npr_paid, start_date = get_premium_info(uid, pid)
            start_date = pd.Timestamp(start_date)
            due_date = start_date + relativedelta(years =1)
            today_date = datetime.datetime.now()
            real_paid = int((today_date - start_date).days/365)
            if pr_once == 'yes' and npr_paid == 0:
                speech_output += 'Hey {} '.format(user_name) + ', your premium amount for policy {} is {} which is not yet paid!'.format(pname, prem_amt) + ' It was due on {} '.format(due_date.strftime("%d")) + 'of {} '.format(due_date.strftime("%B")) + 'in {} .'.format(due_date.strftime("%Y")) + 'Please Pay it ASAP. '
            elif pr_once == 'yes' and npr_paid == 1 :
                speech_output += 'Hey {} '.format(user_name) + ', your premium amount for policy {} was {}! Thanks for paying that before due date.'.format(pname, prem_amt)
            elif pr_once == 'no':
                due_date = start_date + relativedelta(years = npr_paid)
                if npr_paid < real_paid:
                    speech_output += 'Hey {} '.format(user_name) + ', your premium amount for policy {} is {} '.format(pname, prem_amt) +  "and you have only paid {} premium(s) till now! Please pay the remaining ASAP to avoid inconvenience. ".format(npr_paid) 
                elif npr_paid == real_paid:
                    due_date += relativedelta(years =1)
                    speech_output += 'Hey {} '.format(user_name) + ', your premium amount for policy {} is {} '.format(pname, prem_amt) +  "and you have paid {} premiums. ".format(npr_paid) + 'And, your next due date is on {} of {} {} .'.format(due_date.strftime("%d"), due_date.strftime("%B"), due_date.strftime("%Y"))
            print(speech_output, pid)
    else:
        speech_output = 'You have not bought any policies yet! Buy a policy first.'
    reprompt_text = "I said," + speech_output
    should_end_session = False
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))

def get_cbf_recommendation(pid, k=2): # in case of existing user feturn top 2 recommended products based on what he has bought
    df = pd.read_csv('cbf_reco.csv')
    dfp = pd.read_csv('prod.csv')
    pids = df[df.Product == pid].values.tolist()[0][2:]
    return dfp.loc[dfp.id.isin(pids), 'pname'].values.tolist()[:k]
    #return df[df.Product == pid].values.tolist()[0][2:]

def get_a_random_recommendation(): # in case of new user
    #plans = ['Health Maintenance Organization (HMO)', 'Preferred Provider Organization (PPO)', 'Point of Service (POS)', 'High Deductible Health (HDHP)',
    #    'Short term Health Insurance', 'Gap Insurance']
    #return 'You can go with a {} medical health insurance plan'.format(random.choice(plans))
    df =  pd.read_csv('prod.csv')
    return random.choice(df.pname.tolist())
        
def get_recommend_response(intent, session):
    """ An example of a custom intent. Same structure as welcome message, just make sure to add this intent
    in your alexa skill in order for it to work.
    """
    session_attributes = session.get('attributes', {})
    card_title = "Recommendation"
    speech_output = ''
    if 'id' in session_attributes:
        id = int(session_attributes['id'])
        df = pd.read_csv('userprod.csv')
        pid = random.choice(df.loc[(df.uid == id), 'pid'].tolist())
        pnames = get_cbf_recommendation(pid)
        speech_output = 'Top 2 products recommended for you are: {} .'.format(' and '.join(map(str, pnames)))
    else:
        pname = get_a_random_recommendation()
        speech_output = 'You can buy the product {}.'.format(pname)
    
    reprompt_text = "I said," + speech_output
    should_end_session = False
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))

def get_adduser_response(intent, session):
    """ An example of a custom intent. Same structure as welcome message, just make sure to add this intent
    in your alexa skill in order for it to work.
    """
    session_attributes = session.get('attributes', {})
    card_title = "AddUser"
    speech_output = 'Sure. I need some information about you so that I can register you. Tell me your name, age and gender'
    reprompt_text = "I said," + speech_output
    should_end_session = False
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))
        
def get_info_response(intent, session):
    """ An example of a custom intent. Same structure as welcome message, just make sure to add this intent
    in your alexa skill in order for it to work.
    """
    print("SESSION BELOW")
    print(session)
    card_title = "AddInfo"
    session_attributes = session.get('attributes', {})
    session_attributes['name'] = intent['slots']['name']['value']
    session_attributes['age'] = intent['slots']['age']['value']
    session_attributes['gender'] = intent['slots']['gender']['value']
    name, age, gender, married, children, bmi, smoker = session_attributes['name'], session_attributes['age'], \
                    session_attributes['gender'], 'single', 0, \
                    30.22, 'no'
    speech_output = 'Hello {}, registering you with the following information you entered. '.format(name)
    speech_output += 'your are {} years old, you are a {}, you are {}, you have {} number of children, your BMI is {}, you {}'.format( \
                     age, gender, married, children, bmi, 'smoke' if smoker == 'yes' else 'don\'t smoke')
                     
    df = pd.read_csv("user.csv")
    id = df.id.max() + 1 # autoinc id
    df.loc[len(df.index)] = [id, name, age, gender, married, children, bmi, smoker]  
    print(df)
    speech_output = 'Created and added your ID {} to memory! Sorry, Can\'t change the readonly database!'.format(id)
    
    reprompt_text = "I said," + speech_output
    should_end_session = False
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))
          
    
def get_unregister_response(intent, session):
    
    session_attributes = session.get('attributes', {})
    card_title = "Unregister"
    uid = int(session_attributes['id'])
    df = pd.read_csv("user.csv")
    df.drop(df[df.id == uid].index, inplace=True)
    #df.to_csv('user.csv')
    print(df)
    df = pd.read_csv("userprod.csv")
    df.drop(df[df.uid == uid].index, inplace=True)
    #df.to_csv('userprod.csv')
    print(df)
    df = pd.read_csv("userclaim.csv")
    df.drop(df[df.uid == uid].index, inplace=True)
    #df.to_csv('userclaim.csv')
    print(df)
    speech_output = 'Removed your ID {} from memory! Sorry, Can\'t change the readonly database!'.format(uid)
    reprompt_text = "I said," + speech_output
    should_end_session = False
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


def get_welcome_response():
    """ If we wanted to initialize the session to have some attributes we could
    add those here
    """
    session_attributes = {}
    card_title = "Welcome"
    speech_output = "Hello, I am Alexa, your health insurance assistant! You can ask for your benefits, premiums and recommendations! First tell me your user id!"
    # If the user either does not reply to the welcome message or says something
    # that is not understood, they will be prompted again with this text.
    reprompt_text = "I don't know if you heard me, I am your health insurance assitant! Tell me your user id!"
    should_end_session = False
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))

def handle_fallback_intent(): #intent, session):
    card_title = "Fallback Intent"
    #session_attributes = session.get('attributes', {})

    speech_output = "Sorry, I could not understand what you said! " \
                    "Can you say that again? You need to restart from the beginning."
    reprompt_text = 'I said, ' + speech_output
    should_end_session = False
    return build_response({}, build_speechlet_response( #session_attributes
        card_title, speech_output, reprompt_text, should_end_session))

def handle_session_end_request():
    card_title = "Session Ended"
    speech_output = "Thank you for trying Alexa Skill Kit Voice Assistant. " \
                    "Have a nice day! "
    # Setting this to true ends the session and exits the skill.
    should_end_session = True
    return build_response({}, build_speechlet_response(
        card_title, speech_output, None, should_end_session))

# --------------- Events ------------------

def on_session_started(session_started_request, session):
    """ Called when the session starts.
        One possible use of this function is to initialize specific 
        variables from a previous state stored in an external database
    """
    # Add additional code here as needed
    pass

    

def on_launch(launch_request, session):
    """ Called when the user launches the skill without specifying what they
    want
    """
    # Dispatch to your skill's launch message
    return get_welcome_response()


def on_intent(intent_request, session):
    """ Called when the user specifies an intent for this skill """

    intent = intent_request['intent']
    intent_name = intent_request['intent']['name']

    # Dispatch to your skill's intent handlers
    if intent_name == "askid":
        return get_id_response(intent, session)
    elif intent_name == "askbenefit":
        return get_benefit_response(intent, session)
    elif intent_name == "askservice":
        return get_service_response(intent, session)
    elif intent_name == "askpremium":
        return get_premium_response(intent, session)
    elif intent_name == "askproduct":
        return get_product_response(intent, session)
    elif intent_name == "askrecommend":
        return get_recommend_response(intent, session)
    elif intent_name == "adduser":
        return get_adduser_response(intent, session)
    elif intent_name == "askinfo":
        return get_info_response(intent, session)
    elif intent_name == "removeid":
        return get_unregister_response(intent, session)
    elif intent_name == "AMAZON.HelpIntent":
        return get_welcome_response()
    elif intent_name == "AMAZON.CancelIntent" or intent_name == "AMAZON.StopIntent":
        return handle_session_end_request()
    elif intent_name == "AMAZON.FallbackIntent":
        return handle_fallback_intent()
    else:
        raise ValueError("Invalid intent")


def on_session_ended(session_ended_request, session):
    """ Called when the user ends the session.
    Is not called when the skill returns should_end_session=true
    """
    print("on_session_ended requestId=" + session_ended_request['requestId'] +
          ", sessionId=" + session['sessionId'])
    # add cleanup logic here


# --------------- Main handler ------------------

def lambda_handler(event, context):
    """ Route the incoming request based on type (LaunchRequest, IntentRequest,
    etc.) The JSON body of the request is provided in the event parameter.
    """
    print("Incoming request...")

    """
    Uncomment this if statement and populate with your skill's application ID to
    prevent someone else from configuring a skill that sends requests to this
    function.
    """
    # if (event['session']['application']['applicationId'] !=
    #         "amzn1.echo-sdk-ams.app.[unique-value-here]"):
    #     raise ValueError("Invalid Application ID")

    if event['session']['new']:
        on_session_started({'requestId': event['request']['requestId']},
                           event['session'])

    if event['request']['type'] == "LaunchRequest":
        return on_launch(event['request'], event['session'])
    elif event['request']['type'] == "IntentRequest":
        return on_intent(event['request'], event['session'])
    elif event['request']['type'] == "SessionEndedRequest":
        return on_session_ended(event['request'], event['session'])
