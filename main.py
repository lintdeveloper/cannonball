# Cannonball Internal API
# IMPORTS
import os
import urllib
import json
import math
from bson import Binary, Code
from bson.json_util import dumps, loads
from bson.objectid import ObjectId
from flask import Flask, render_template, request, flash, redirect, url_for, session, logging, jsonify
from flask_pymongo import PyMongo
from slackclient import SlackClient
# END IMPORTS

# HERE API
here_appId = "yDIiTl1dh0pFhmMq7Ggf"
here_appCode = "Lz4ozsXQflfSlfcFpG74jw"
here_baseURL = "https://pos.api.here.com/positioning/v1/"
# END HERE

# Define App requirements
app = Flask(__name__, static_folder="../static", template_folder="../static")

# SLACK API
slack_client = SlackClient("xoxp-460967073045-460768312130-461837855431-1d2fa2229b2ae01e5d78e7279be3a66b")

# CONFIG
app.config["MONGO_URI"] = "mongodb://" + urllib.parse.quote("cannonball") + ":" + urllib.parse.quote("test") + "@cluster0-shard-00-00-pevs9.gcp.mongodb.net:27017,cluster0-shard-00-01-pevs9.gcp.mongodb.net:27017,cluster0-shard-00-02-pevs9.gcp.mongodb.net:27017/CannonballDB?ssl=true&replicaSet=Cluster0-shard-0&authSource=admin&retryWrites=true"
app.debug=True
mongo = PyMongo(app)

@app.route("/")
def index():
    return("<h1>Cannonball!</h1>")

@app.route("/getEvents", methods=['GET'])
def events():
    events = mongo.db.events.find()
    app.logger.info(events)
    return dumps(events)

# {{URL}}/getUsersForEvent?event={event name}
@app.route("/getUsersForEvent", methods = ['GET'])
def usersByEvent():
    eventName = request.args.get('name')
    app.logger.info(eventName)
    event = mongo.db.events.find_one({'name': eventName})
    app.logger.info(event)
    users = event.get('checkedInUsers')
    app.logger.info(users)

    userDict = {}
    i = 0
    for uid in users:
        elt = mongo.db.users.find_one({"_id": uid})
        userDict[i] = elt
        i += 1
    return dumps(userDict)

@app.route("/newUser", methods=['POST'])
def insertNewUser():
    newUser = request.get_json()
    app.logger.info(newUser)
    mongo.db.users.insert(newUser)
    return dumps(newUser)

@app.route("/newGroup", methods=['POST'])
def insertNewGroup():
    newGroup = request.get_json()
    app.logger.debug(newGroup)
    newusers = []
    newadmins = []
    for user in newGroup.get('users'):
        uid = str(user['$oid'])
        obj = ObjectId(uid)
        newusers.append(obj)

    for user in newGroup.get('admins'):
        uid = str(user['$oid'])
        obj = ObjectId(uid)
        newadmins.append(obj)

    creator = newGroup.get('creator')
    uid = str(user['$oid'])
    obj = ObjectId(uid)
    newcreator = obj

    app.logger.debug(newusers)
    newGroup['users'] = newusers
    newGroup['admins'] = newadmins
    newGroup['creator'] = newcreator
    app.logger.info(newGroup)
    mongo.db.groups.insert(newGroup)
    return dumps(newGroup)

@app.route("/newEvent", methods=['POST'])
def insertNewEvent():
    newEvent = request.get_json()
    name = newEvent.get('name')
    app.logger.info(newEvent)
    gid = str(newEvent.get('groupid')['$oid'])
    app.logger.info(gid)
    newEvent['groupid'] = ObjectId(gid)
    app.logger.info(newEvent)
    mongo.db.events.insert(newEvent)
    try:
        event = mongo.db.events.find_one({'name': name})
        eid = event.get('_id')
    except:
        return "Could not find newly created event. Perhaps your group does not exist"
    try:
        group = mongo.db.groups.find_one({'_id': ObjectId(gid)})
    except:
        return "Group not found, please create a new group first."
    groupEvents = group.get('events')
    if eid not in groupEvents:
        mongo.db.groups.update_one({'_id': ObjectId(gid)},{'$push':{'events':eid}})
    return dumps(newEvent)

@app.route("/checkInUser", methods=['POST'])
def checkInUser():
    app.logger.info('recieved')
    newCheckIn = request.get_json()
    app.logger.info(newCheckIn)
    event = newCheckIn.get('name')
    targetEvent = mongo.db.events.find_one({'name': event})
    useremail = newCheckIn.get('email')
    targetUser = mongo.db.users.find_one({'email': useremail})
    targetGroup = targetEvent.get('groupid')
    groups = targetUser.get('groups')

    if targetGroup not in groups:
        myId = targetUser.get('_id')
        mongo.db.users.update_one({'_id': myId}, {'$push': {'groups': targetGroup}})

    app.logger.info(targetUser)
    app.logger.info(targetEvent)

    userId = targetUser.get("_id")
    myId = targetEvent.get("_id")
    if myId != None:
        event = mongo.db.events.find_one({'_id':myId})
        if userId not in event['checkedInUsers']:
            mongo.db.events.update_one({'_id': myId}, {'$push': {'checkedInUsers': userId}})
            return "Successfully checked in"
        else:
            return "Looks like you're already checked in!"

@app.route("/userGroups", methods=['POST'])
def getAllGroupsForUser():
    app.logger.info('recieved')
    theUser = request.get_json()
    useremail = theUser.get('email')
    targetUser = mongo.db.users.find_one({'email': useremail})
    groups = targetUser.get('groups')
    return dumps(groups)

@app.route("/exportToSlack", methods=['POST'])
def slackExport():
    groupName = request.args.get('group')
    group = mongo.db.groups.find_one({"name": groupName})
    users = group.get('users')

    team = slack_client.api_call("users.list")
    app.logger.debug(team)
    teamEmails = ()
    for user in team:
        try:
            app.logger.debug(user)
            email = user.get('profile').get('email')
            teamEmails.add(email)
        except:
            pass

    emails =()
    for user in users:
        u = mongo.db.users.find_one({"_id": user})
        email = u.get('email')
        if email not in teamEmails:
            callstring = "users.admin.invite?email={}".format(email)
            app.logger.info(callstring)
            slack_client.api_call(callstring)


    return "invites sent"

@app.route("/getNearbyEvents", methods = ['POST'])
def getNearbyEvents():
    app.logger.info('recieved')
    location = request.get_json()
    curLong = location.get('longitude')
    curLat = location.get('latitude')
    app.logger.info(curLong)
    app.logger.info(curLat)
    myEvents = mongo.db.events.find({})
    nearbyEvents = []
    for x in myEvents:
        if distance(float(curLat), float(x.get('latitude')), float(curLong), float(x.get('longitude'))) < 2 :
            nearbyEvents.append(x.get('name'))
    return dumps(nearbyEvents)

@app.route("/pingAllMembers", methods = ['POST'])
def getAllMembers():
    app.logger.info('recieved')
    groupinfo = request.get_json()  
    groupName = groupinfo.get('name')
    targetGroup = mongo.db.groups.find_one({"name": groupName})
    groupMembers = targetGroup.get('users')
    return dumps(groupMembers)






def distance(lat1, lat2, long1, long2):
    dlong = long2 - long1
    dlat = lat2 -lat1
    a = (math.sin(dlat/2))**2 + math.cos(lat1) * math.cos(lat2) * (math.sin(dlong/2))**2
    c = 2 * math.atan2( math.sqrt(a), math.sqrt(1-a) )
    d = 3961 * c
    return d


# LAUNCH APP
if __name__ == "__main__":
        port = int(os.environ.get("PORT", 5000))
        app.logger.info("Getting Flask up and running...\n")
        if slack_client.api_call("api.test") is not None:
            app.logger.info("Connected to Slack!")
        app.run(host = '127.0.0.1' , port = port)
