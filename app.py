from flask import Flask, render_template, url_for, request, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from queue import Queue
from typing import List
from secrets import riot_api_token

import threading
import json
import requests

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
            queue.put({'request_type': 'get_players_in_league', 'league': 'grandmaster'})
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
    endpoint = '/tft/match/v1/matches/by-puuid/{puuid}/ids?count={count}'.format(puuid=puuid, count=5)
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
        else:
            queue.add({'request_type': 'get_match_data', 'match_id': match_id})

def hashRegion(region: str, summoner_name: str) -> int:
    return hash(region +summoner_name )

champion_set = {'TFT3_ahri','TFT3_annie','TFT3_ashe','TFT3_aurelionsol','TFT3_bard','TFT3_blitzcrank','TFT3_caitlyn','TFT3_cassiopeia','TFT3_darius','TFT3_ekko','TFT3_ezreal','TFT3_fiora','TFT3_fizz','TFT3_gangplank','TFT3_gnar','TFT3_graves','TFT3_illaoi','TFT3_irelia','TFT3_janna','TFT3_jarvaniv','TFT3_jayce','TFT3_jhin','TFT3_jinx','TFT3_karma','TFT3_kogmaw','TFT3_leona','TFT3_lucian','TFT3_lulu','TFT3_malphite','TFT3_masteryi','TFT3_mordekaiser','TFT3_nautilus','TFT3_neeko','TFT3_nocturne','TFT3_poppy','TFT3_rakan','TFT3_riven','TFT3_rumble','TFT3_shaco','TFT3_shen','TFT3_soraka','TFT3_syndra','TFT3_teemo','TFT3_thresh','TFT3_twistedfate','TFT3_urgot','TFT3_vayne','TFT3_vi','TFT3_viktor','TFT3_wukong','TFT3_xayah','TFT3_xerath','TFT3_xinzhao','TFT3_yasuo','TFT3_zed','TFT3_ziggs','TFT3_zoe'}
comp_statistics = {}
all_games = 0



def getAllSublists(comp, extra):
    if extra == 0:
        return [comp]
    else:
        sublists = []
        for i in range(len(comp)):
            temp = comp[0:i] + comp[i+1:]
            ret = getAllSublists(temp, extra-1)
            for returned_sublist in ret:
                sublists.append(returned_sublist)
        return sublists

def matchDataStats(match_data: List[MatchData]) -> None:
    global comp_statistics, all_games
    for match in match_data:
        all_games += 1
        js = json.loads(match.content)
        participants = js['participants']
        for participant in participants:
            comp = []
            placement = participant['placement']
            for unit in participant['units']:
                character_id = unit['character_id']
                comp.append(character_id)
            extra = len(comp)-8
            if extra >= 0:
                all_sublists = getAllSublists(comp, extra)
                for sublist in all_sublists:
                    key = repr(sorted(sublist))
                    if key not in comp_statistics:
                        comp_statistics[key] = { 'winrate': 0, 'games': 0, 'avg_placement': 0, 'sum_placements': 0, 'wins': 0, 'top_4_count': 0, 'top_4_rate': 0 }
                    stats = comp_statistics.get(key)
                    stats['games'] += 1
                    stats['wins'] += 1 if placement == 1 else 0
                    stats['top_4_count'] += 1 if placement < 5 else 0
                    stats['sum_placements'] += placement
    for comp in comp_statistics:
        c = comp_statistics.get(comp)
        c['winrate'] = c['wins']/c['games']
        c['avg_placement'] = c['sum_placements']/c['games']
        c['top_4_rate'] = c['top_4_count']/c['games']

if __name__ == "__main__":
    start()
    app.run(debug=False)
