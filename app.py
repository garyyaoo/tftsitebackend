from flask import Flask, render_template, url_for, request, redirect, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from queue import Queue
from typing import List
# from secrets import riot_api_token

import itertools
import threading
import json
import requests

riot_api_token = 'RGAPI-a7806328-77f6-405e-abb3-aa66c8d5569b'

riot_token = riot_api_token
headers={ 'X-Riot-Token': riot_token}

queue = Queue()
thread = None

stored_matches ={""}
trait_set = {'tft3_ahri': ['sorcerer', 'starguardian'],'tft3_annie': ['mechpilot', 'sorcerer'],'tft3_ashe': ['celestial', 'sniper'],'tft3_aurelionsol': ['rebel', 'starship'],'tft3_bard': ['astro', 'mystic'],'tft3_blitzcrank': ['chrono', 'brawler'],'tft3_caitlyn': ['chrono', 'sniper'],'tft3_cassiopeia': ['battlecast','mystic'],'tft3_darius': ['spacepirate', 'manareaver'],'tft3_ekko': ['cybernetic','infiltrator'],'tft3_ezreal': ['chrono','blaster'],'tft3_fiora': ['cybernetic', 'blademaster'],'tft3_fizz': ['infiltrator', 'mechpilot'],'tft3_gangplank': ['demolitionist', 'spacepirate','mercenary'],'tft3_gnar': ['astro','brawler'],'tft3_graves': ['spacepirate','blaster'],'tft3_illaoi': ['battlecast','brawler'],'tft3_irelia': ['cybernetic','manareaver','blademaster'],'tft3_janna': ['starguardian','paragon'],'tft3_jarvaniv': ['protector','darkstar'],'tft3_jayce': ['spacepirate','vanguard'],'tft3_jhin': ['sniper','darkstar'],'tft3_jinx': ['rebel','blaster'],'tft3_karma': ['darkstar','mystic'],'tft3_kogmaw': ['battlecast','blaster'],'tft3_leona': ['vanguard','cybernetic'],'tft3_lucian': ['cybernetic','blaster'],'tft3_lulu': ['celestial','mystic'],'tft3_malphite': ['rebel','brawler'],'tft3_masteryi': ['rebel','blademaster'],'tft3_mordekaiser': ['vanguard','darkstar'],'tft3_nautilus': ['astro','vanguard'],'tft3_neeko': ['starguardian','protector'],'tft3_nocturne': ['infiltrator','battlecast'],'tft3_poppy': ['starguardian','vanguard'],'tft3_rakan': ['celestial','protector'],'tft3_riven': ['chrono','blademaster'],'tft3_rumble': ['demolitionist','mechpilot'],'tft3_shaco': ['darkstar','infiltrator'],'tft3_shen': ['chrono','blademaster'],'tft3_soraka': ['starguardian','mystic'],'tft3_syndra': ['sorcerer','starguardian'],'tft3_teemo': ['sniper','astro'],'tft3_thresh': ['chrono','manareaver'],'tft3_twistedfate': ['chrono','sorcerer'],'tft3_urgot': ['protector','battlecast'],'tft3_vayne': ['sniper','cybernetic'],'tft3_vi': ['brawler','cybernetic'],'tft3_viktor': ['battlecast','sorcerer'],'tft3_wukong': ['chrono','vanguard'],'tft3_xayah': ['blademaster','celestial'],'tft3_xerath': ['darkstar','sorcerer'],'tft3_xinzhao': ['celestial','protector'],'tft3_yasuo': ['rebel','blademaster'],'tft3_zed': ['rebel','infiltrator'],'tft3_ziggs': ['rebel','demolitionist'],'tft3_zoe': ['sorcerer','starguardian']}
trait_count = {'astro': [3],'celestial': [2,4,6], 'chrono': [2,4,6,8], 'cybernetic': [3,6], 'darkstar': [2,4,6,8], 'sorcerer': [2,4,6], 'spacepirate': [2,4], 'mechpilot': [3], 'rebel': [3,6,9], 'starguardian': [3,6,9], 'infiltrator': [2,4,6],'blaster': [2,4],'brawler': [2,4],'mercenary': [1],'demolitionist': [2],'protector': [2,4,6],'mystic': [2,4],'manareaver': [2],'blademaster': [3,6,9],'sniper': [2,4],'starship': [1],'battlecast': [2,4,6,8],'paragon': [1],'vanguard': [2,4,6]}
comp_statistics = {}
trait_statistics = {}
all_games = 0

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

class TempMatchData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.String(64), nullable=False)
    content = db.Column(db.String(32768), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return '<TempMatchData %r>' % self.match_id

@app.route('/stop', methods=['GET'])
def stop():
    cancel()
    return visualizeQueue()

@app.route('/start', methods=['GET'])
def start_endpoint():
    start()
    return 

@app.route('/queue', methods=['GET'])
def visualize():
    puuids = Puuid.query.all()
    match_ids = MatchData.query.all()

    return render_template('visualize.html', queue_str=puuids, match_data_str=match_ids)

@app.route('/stats', methods=['GET'])
def getStats():
    sort = "games" if request.args.get('sort') is None else request.args.get('sort')
    count = request.args.get('count')
    count = 10 if count is None or not count.isnumeric() else int(count)
    if sort not in ["games", "winrate", "placement"]:
        sort="games"

    global all_games
    response = Response(
        response= json.dumps({'games': all_games, 'comps': getSortedStatistics(sort, count)}),
        status=200
    )
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['content-type'] = 'application/json'
    return response

def getSortedStatistics(sort: str, count: int):
    global trait_statistics
    sorted_ret = None
    if (sort == "games"):
        sorted_ret = [{'traits':key, 'stats':value} for key, value in sorted(trait_statistics.items(), key=lambda x: (x[1]['games'], x[1]['winrate']), reverse=True)[0:count]]
    if (sort == "winrate"):
        sorted_ret = [{'traits':key, 'stats':value} for key, value in sorted(trait_statistics.items(), key=lambda x: (x[1]['winrate'], x[1]['games']) if x[1]['games'] > 299 else (-1, -1), reverse=True)[0:count]]
    if (sort == "placement"):
        sorted_ret = [{'traits':key, 'stats':value} for key, value in sorted(trait_statistics.items(), key=lambda x: (x[1]['avg_placement'], x[1]['games']) if x[1]['games'] > 299 else (10, 10), reverse=False)[0:count]]
    for comp in sorted_ret:
        comp['stats']['variations'] = dict(itertools.islice({ key: value for key, value in sorted(comp['stats']['variations'].items(), key=lambda x: x[1]['games'], reverse=True)}.items(), 3))
    return sorted_ret

def start():
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
    
    thread = threading.Timer(2.5, start)
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
            if Puuid.query.filter_by(id=hashRegion('NA', e['summonerName'])).scalar() is None:
                queue.put({'request_type': 'get_summoner_info', 'summoner_name': e['summonerName']})
            else:
                puuid = Puuid.query.filter_by(id=hashRegion('NA', e['summonerName'])).first().puuid
                queue.put({'request_type': 'get_player_match_history', 'puuid': puuid})

def getSummonerInfo(summoner_name: str) -> None:
    global headers, queue
    if Puuid.query.filter_by(id=hashRegion('NA', summoner_name)).scalar() is None:
        base_url = 'https://na1.api.riotgames.com'
        endpoint = '/tft/summoner/v1/summoners/by-name/{summoner_name}'.format(summoner_name=summoner_name)
        r = requests.get(base_url + endpoint, headers=headers)
        if r.ok:
            v = json.loads(r.text)
            puuid = Puuid(id=hashRegion('NA', summoner_name), puuid=v['puuid'], username=summoner_name)
            print('hashRegion {}'.format(hashRegion('NA', summoner_name)))
            db.session.add(puuid)
            db.session.commit()
            queue.put({'request_type': 'get_player_match_history', 'puuid': v['puuid']})
            print('from db {}'.format(Puuid.query.filter_by(username=summoner_name).first().id))
            if Puuid.query.filter_by(username=summoner_name).first().id != hashRegion('NA', summoner_name):
                Puuid.query.filter_by(username=summoner_name).delete()
                db.session.commit()
                new_puuid = Puuid(id=hashRegion('NA', summoner_name), puuid=v['puuid'], username=summoner_name)
                db.session.add(new_puuid)
                db.session.commit()
    else:
        puuid = Puuid.query.filter_by(id=hashRegion('NA', summoner_name)).first().puuid
        queue.put({'request_type': 'get_player_match_history', 'puuid': puuid})

def getPlayerMatchHistory(puuid: str) -> None:
    global headers, queue, stored_matches
    base_url = 'https://americas.api.riotgames.com'
    endpoint = '/tft/match/v1/matches/by-puuid/{puuid}/ids?count={count}'.format(puuid=puuid, count=5)
    r = requests.get(base_url+endpoint, headers=headers)
    if r.ok:
        print('get history ok')
        v = json.loads(r.text)
        for match_id in v:
            if match_id not in stored_matches and MatchData.query.filter_by(id=hash(match_id)).scalar() is None:
                queue.put({'request_type': 'get_match_data', 'match_id': match_id })
                stored_matches.add(match_id)

def getMatchData(match_id: str) -> None:
    global headers, stored_matches
    base_url = 'https://americas.api.riotgames.com'
    endpoint = '/tft/match/v1/matches/{match_id}'.format(match_id=match_id)
    r = requests.get(base_url + endpoint, headers=headers)
    if r.ok:
        print('matchData OK')
        v = json.loads(r.text)
        match_data = MatchData(id=hash(match_id), match_id=match_id, content=json.dumps(v['info']))
        # temp_match_data = TempMatchData(id=hash(match_id), match_id=match_id, content=json.dumps(v['info']))
        stored_matches.add(match_id)
        matchDataStats([match_data])
        try:
            db.session.add(match_data)
            # db.session.add(temp_match_data)
            db.session.commit()
        except:
            db.session.rollback()
    else:
        queue.add({'request_type': 'get_match_data', 'match_id': match_id})

def hashRegion(region: str, summoner_name: str) -> int:
    return hash(region+summoner_name)

def matchDataStats(match_data: List[MatchData]) -> None:
    global all_games, trait_statistics
    for match in match_data:
        all_games += 1
        js = json.loads(match.content)
        participants = js['participants']
        for participant in participants:
            comp = []
            placement = participant['placement']
            for unit in participant['units']:
                character_id = unit['character_id']
                comp.append(character_id.lower())
            extra = len(comp)-8
            if extra >= 0:
                all_sublists = getAllSublists(comp, extra, 0)
                for sublist in all_sublists:
                    [ trait_id_key, traits ] = compToTraits(sublist)
                    comp_key = repr(sorted(sublist))

                    if trait_id_key not in trait_statistics:
                        trait_statistics[trait_id_key] = { 'winrate': 0, 'games': 0, 'avg_placement': 0, 'sum_placements': 0, 'wins': 0, 'top_4_count': 0, 'top_4_rate': 0, 'variations': {}}
                    trait = trait_statistics[trait_id_key]
                    trait['games'] += 1
                    trait['wins'] += 1 if placement == 1 else 0
                    trait['top_4_count'] += 1 if placement < 5 else 0
                    trait['sum_placements'] += placement

                    trait['winrate'] = trait['wins']/trait['games']
                    trait['avg_placement'] = trait['sum_placements']/trait['games']
                    trait['top_4_rate'] = trait['top_4_count']/trait['games']
                    
                    if comp_key not in trait['variations']:
                        trait['variations'][comp_key] = { 'winrate': 0, 'games': 0, 'avg_placement': 0, 'sum_placements': 0, 'wins': 0, 'top_4_count': 0, 'top_4_rate': 0, 'traits': traits }
                    comp_stats = trait['variations'][comp_key]
                    comp_stats['games'] += 1
                    comp_stats['wins'] += 1 if placement == 1 else 0
                    comp_stats['top_4_count'] += 1 if placement < 5 else 0
                    comp_stats['sum_placements'] += placement

                    comp_stats['winrate'] = comp_stats['wins']/comp_stats['games']
                    comp_stats['avg_placement'] = comp_stats['sum_placements']/comp_stats['games']
                    comp_stats['top_4_rate'] = comp_stats['top_4_count']/comp_stats['games']

def getAllSublists(comp, extra, first):
    if extra == 0 or first == len(comp)-1:
        return [comp]
    else:
        sublists = []
        for i in range(first, len(comp)):
            temp = comp[0:i] + comp[i+1:]
            ret = getAllSublists(temp, extra-1, i)
            for returned_sublist in ret:
                sublists.append(returned_sublist)
        return sublists

def compToTraits(comp):
    global trait_set, trait_count
    unit_set = {""}
    traits = {}
    for unit in comp:
        if unit not in unit_set:
            unit_set.add(unit)
            for trait in trait_set[unit]:
                traits[trait] = traits.get(trait, 0) + 1
    for key in list(traits):
        highest = max([x if x <= traits[key] else 0 for x in trait_count[key]])
        if highest == 0:
            traits.pop(key)
        else:
            traits[key] = highest
    sorted_dict = sorted(traits.items(), key=lambda x: (x[1], x[0]), reverse=True)
    return [repr([repr(value) + ' ' + key for key, value in sorted_dict[0:2]]), dict(sorted_dict)]


if __name__ == "__main__":
    start()
    matchDataStats(MatchData.query.all()) 
    app.run(debug=True)
