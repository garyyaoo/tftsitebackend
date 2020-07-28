from flask import Flask, render_template, url_for, request, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from queue import Queue

import threading
import json
import requests
from secrets import riot_api_token

riot_token = riot_api_token
headers={ 'X-Riot-Token': riot_token}

stop_requesting = False
queue = Queue()
thread = None

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
db = SQLAlchemy(app)

class Puuid(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    puuid = db.Column(db.String(4096), nullable=False)
    username = db.Column(db.String(4096), nullable=False)

    def __repr__(self):
        return '<Puuid %r>' % self.username

class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(32), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

class MatchData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.String(64), nullable=False)
    content = db.Column(db.String(32768), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return '<MatchData%r>' % self.match_id

@app.route('/', methods=['POST', 'GET'])
def index():
    if request.method == 'POST':
        task_content = request.form['content']
        new_task = Todo(content=task_content)

        try:
            db.session.add(new_task)
            db.session.commit()
            return redirect('/')
        except:
            return 'There was an issue adding your task'

    else:
        tasks = Todo.query.order_by(Todo.date_created).all()
        return render_template('index.html', tasks=tasks, )

@app.route('/delete/<int:id>')
def delete(id):
    task_to_delete = Todo.query.get_or_404(id)

    try:
        db.session.delete(task_to_delete)
        db.session.commit()
        return redirect('/')
    except:
        return 'There was a problem deleting that task'

@app.route('/update/<int:id>', methods=['GET', 'POST'])
def update(id):
    task = Todo.query.get_or_404(id)
    if request.method == 'POST':
        task.content = request.form['content']

        try:
            db.session.commit()
            return redirect('/')
        except:
            return "There was an issue updating your task   "
    else:
        return render_template('update.html', task=task)

@app.route('/stop', methods=['GET'])
def stop():
    cancel()
    return visualizeQueue()

@app.route('/queue', methods=['GET'])
def visualize():
    puuids = Puuid.query.all()
    match_ids = MatchData.query.all()


    return render_template('visualize.html', queue_str=puuids, match_data_str=match_ids)

def start():
    if not stop_requesting:
        global thread, queue
        if queue.qsize() == 0:
            queue.put({'request_type': 'get_players_in_league', 'league': 'challenger'})
            # queue.put({'request_type': 'get_players_in_league', 'league': 'grandmaster'})
            # queue.put({'request_type': 'get_players_in_league', 'league': 'master'})
        
        req = queue.get()
        print(req)
        request_type = req['request_type']
        if request_type == 'get_players_in_league':
            getPlayersInLeague(req['league'])
        elif request_type == 'get_summoner_info':
            getSummonerInfo(req['summoner_name'])
        elif request_type == 'get_player_match_history':
            getPlayerMatchHistory(req['puuid'])
        elif request_type == 'get_match_data':
            getMatchData(req['match_id'])
        
        thread = threading.Timer(1.21, start)
        thread.start()

def visualizeQueue():
    global queue
    return list(queue.queue).__repr__()

def cancel():
    global thread
    thread.cancel()

def getPlayersInLeague(league: str) -> None:
    global headers, queue
    base_url = 'https://na1.api.riotgames.com'
    endpoint = '/tft/league/v1/{league}'.format(league=league)
    r = requests.get(base_url + endpoint, headers=headers)
    if r.ok:
        v = json.loads(r.text)
        entries = v['entries']
        for e in entries:
            queue.put({'request_type': 'get_summoner_info', 'summoner_name': e['summonerName']})

def getSummonerInfo(summoner_name: str) -> None:
    global headers, queue
    if Puuid.query.filter_by(id=hashRegion('NA', summoner_name)).scalar() is None:
        base_url = 'https://na1.api.riotgames.com'
        endpoint = '/tft/summoner/v1/summoners/by-name/{summoner_name}'.format(summoner_name=summoner_name)
        r = requests.get(base_url + endpoint, headers=headers)
        if r.ok:
            v = json.loads(r.text)
            puuid = Puuid(id=hashRegion('NA', summoner_name) ,puuid=v['puuid'], username=v['name'])
            db.session.add(puuid)
            db.session.commit()
            queue.put({'request_type': 'get_player_match_history', 'puuid': v['puuid']})
    else:
        puuid = Puuid.query.filter_by(id=hashRegion('NA', summoner_name)).first().puuid
        queue.put({'request_type': 'get_player_match_history', 'puuid': puuid})

def getPlayerMatchHistory(puuid: str) -> None:
    global headers, queue
    base_url = 'https://americas.api.riotgames.com'
    endpoint = '/tft/match/v1/matches/by-puuid/{puuid}/ids?count={count}'.format(puuid=puuid, count=20)
    r = requests.get(base_url+endpoint, headers=headers)
    if r.ok:
        print('get history ok')
        v = json.loads(r.text)
        for match_id in v:
            queue.put({'request_type': 'get_match_data', 'match_id': match_id })

def getMatchData(match_id: str) -> None:
    global headers
    if MatchData.query.filter_by(id=hash(match_id)).first() is None:
        base_url = 'https://americas.api.riotgames.com'
        endpoint = '/tft/match/v1/matches/{match_id}'.format(match_id=match_id)
        r = requests.get(base_url + endpoint, headers=headers)
        if r.ok:
            print('matchData OK')
            v = json.loads(r.text)
            match_data = MatchData(id=hash(match_id), match_id=match_id, content=json.dumps(v['info']))
            try:
                db.session.add(match_data)
                db.session.commit()
            except:
                db.session.rollback()

def hashRegion(region: str, summoner_name: str) -> int:
    return hash(region +summoner_name )

if __name__ == "__main__":
    start()
    app.run(debug=False)
