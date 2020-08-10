from flask import Flask, render_template, url_for, request, redirect, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from queue import Queue
from typing import List
# from secrets import riot_api_token

import threading
import json
import requests


riot_token = riot_api_token
headers={ 'X-Riot-Token': riot_token}

queue = Queue()
thread = None

stored_matches ={""}
trait_set = {'tft3_ahri': ['sorcerer', 'starguardian'],'tft3_annie': ['mechpilot', 'sorcerer'],'tft3_ashe': ['celestial', 'sniper'],'tft3_aurelionsol': ['rebel', 'starship'],'tft3_bard': ['astro', 'mystic'],'tft3_blitzcrank': ['chrono', 'brawler'],'tft3_caitlyn': ['chrono', 'sniper'],'tft3_cassiopeia': ['battlecast','mystic'],'tft3_darius': ['spacepirate', 'manareaver'],'tft3_ekko': ['cybernetic','infiltrator'],'tft3_ezreal': ['chrono','blaster'],'tft3_fiora': ['cybernetic', 'blademaster'],'tft3_fizz': ['infiltrator', 'mechpilot'],'tft3_gangplank': ['demolitionist', 'spacepirate','mercenary'],'tft3_gnar': ['astro','brawler'],'tft3_graves': ['spacepirate','blaster'],'tft3_illaoi': ['battlecast','brawler'],'tft3_irelia': ['cybernetic','manareaver','blademaster'],'tft3_janna': ['starguardian','paragon'],'tft3_jarvaniv': ['protector','darkstar'],'tft3_jayce': ['spacepirate','vanguard'],'tft3_jhin': ['sniper','darkstar'],'tft3_jinx': ['rebel','blaster'],'tft3_karma': ['darkstar','mystic'],'tft3_kogmaw': ['battlecast','blaster'],'tft3_leona': ['vanguard','cybernetic'],'tft3_lucian': ['cybernetic','blaster'],'tft3_lulu': ['celestial','mystic'],'tft3_malphite': ['rebel','brawler'],'tft3_masteryi': ['rebel','blademaster'],'tft3_mordekaiser': ['vanguard','darkstar'],'tft3_nautilus': ['astro','vanguard'],'tft3_neeko': ['starguardian','protector'],'tft3_nocturne': ['infiltrator','battlecast'],'tft3_poppy': ['starguardian','vanguard'],'tft3_rakan': ['celestial','protector'],'tft3_riven': ['chrono','blademaster'],'tft3_rumble': ['demolitionist','mechpilot'],'tft3_shaco': ['darkstar','infiltrator'],'tft3_shen': ['chrono','blademaster'],'tft3_soraka': ['starguardian','mystic'],'tft3_syndra': ['sorcerer','starguardian'],'tft3_teemo': ['sniper','astro'],'tft3_thresh': ['chrono','manareaver'],'tft3_twistedfate': ['chrono','sorcerer'],'tft3_urgot': ['protector','battlecast'],'tft3_vayne': ['sniper','cybernetic'],'tft3_vi': ['brawler','cybernetic'],'tft3_viktor': ['battlecast','sorcerer'],'tft3_wukong': ['chrono','vanguard'],'tft3_xayah': ['blademaster','celestial'],'tft3_xerath': ['darkstar','sorcerer'],'tft3_xinzhao': ['celestial','protector'],'tft3_yasuo': ['rebel','blademaster'],'tft3_zed': ['rebel','infiltrator'],'tft3_ziggs': ['rebel','demolitionist'],'tft3_zoe': ['sorcerer','starguardian']}
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
    if sort not in ["games", "wins", "placement"]:
        sort="games"

    global comp_statistics, all_games
    response = Response(
        response= json.dumps({'games': all_games, 'comps': getSortedStatistics(sort, count)}),
        status=200
    )
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['content-type'] = 'application/json'
    print('count {}'.format(count))
    print('sort {}'.format(sort))
    return response

def getSortedStatistics(sort: str, count: int):
    global trait_statistics
    if (sort == "games"):
        return [{'traits':key, 'stats':value} for key, value in sorted(trait_statistics.items(), key=lambda x: (x[1]['games'], x[1]['winrate']), reverse=True)[0:count]]
    if (sort == "wins"):
        return [{'traits':key, 'stats':value} for key, value in sorted(trait_statistics.items(), key=lambda x: (x[1]['winrate'], x[1]['games']) if x[1]['games'] > 99 else (-1, -1), reverse=True)[0:count]]
    if (sort == "placement"):
        return [{'traits':key, 'stats':value} for key, value in sorted(trait_statistics.items(), key=lambda x: (x[1]['avg_placement'], x[1]['games']) if x[1]['games'] > 99 else (10, 10), reverse=False)[0:count]]

def start():
    global thread, queue
    if queue.qsize() == 0:
        queue.put({'request_type': 'get_players_in_league', 'league': 'challenger'})
        queue.put({'request_type': 'get_players_in_league', 'league': 'grandmaster'})
        queue.put({'request_type': 'get_players_in_league', 'league': 'master'})
    
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
    global headers, stored_matches
    if match_id not in stored_matches and MatchData.query.filter_by(id=hash(match_id)).first() is None:
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
                db.session.add(temp_match_data)
                db.session.commit()
            except:
                db.session.rollback()
        else:
            queue.add({'request_type': 'get_match_data', 'match_id': match_id})

def hashRegion(region: str, summoner_name: str) -> int:
    return hash(region +summoner_name )

def matchDataStats(match_data: List[MatchData]) -> None:
    global comp_statistics, all_games, trait_statistics
    temp_comp_statistics = {}
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
                temp_trait_stats = {}
                all_sublists = getAllSublists(comp, extra, 0)
                for sublist in all_sublists:
                    trait_key = compToTraits(sublist)
                    key = repr(sorted(sublist))

                    if trait_key not in temp_trait_stats:
                        temp_trait_stats[trait_key] = { 'winrate': 0, 'games': 0, 'avg_placement': 0, 'sum_placements': 0, 'wins': 0, 'top_4_count': 0, 'top_4_rate': 0, 'variations': {}}
                        trait = temp_trait_stats[trait_key]
                        trait['games'] += 1
                        trait['wins'] += 1 if placement == 1 else 0
                        trait['top_4_count'] += 1 if placement < 5 else 0
                        trait['sum_placements'] += placement
                    
                    if key not in temp_comp_statistics:
                        temp_comp_statistics[key] = { 'winrate': 0, 'games': 0, 'avg_placement': 0, 'sum_placements': 0, 'wins': 0, 'top_4_count': 0, 'top_4_rate': 0 }
                    stats = temp_comp_statistics.get(key)
                    stats['games'] += 1
                    stats['wins'] += 1 if placement == 1 else 0
                    stats['top_4_count'] += 1 if placement < 5 else 0
                    stats['sum_placements'] += placement

                    stats['winrate'] = stats['wins']/stats['games']
                    stats['avg_placement'] = stats['sum_placements']/stats['games']
                    stats['top_4_rate'] = stats['top_4_count']/stats['games']

                    if key not in temp_trait_stats[trait_key]['variations']:
                        temp_trait_stats[trait_key]['variations'][key] = stats

                for trait in temp_trait_stats:
                    if trait not in trait_statistics:
                        trait_statistics[trait] = temp_trait_stats[trait]
                    else:
                        traits = trait_statistics[trait]
                        temp_traits = temp_trait_stats[trait]
                        traits['games'] += temp_traits['games']
                        traits['wins'] += temp_traits['wins']
                        traits['top_4_count'] += temp_traits['top_4_count']
                        traits['sum_placements'] += temp_traits['sum_placements']
                        for variation in temp_traits['variations']:
                            if variation not in traits['variations']:
                                traits['variations'][variation] = temp_traits['variations'][variation]
                            else:
                                temp_variation = traits['variations'][variation]
                                temp_variation['games'] += temp_traits['games']
                                temp_variation['wins'] += temp_traits['wins']
                                temp_variation['top_4_count'] += temp_traits['top_4_count']
                                temp_variation['sum_placements'] += temp_traits['sum_placements']        
                    trait_statistics[trait]['winrate'] = trait_statistics[trait]['wins']/trait_statistics[trait]['games']
                    trait_statistics[trait]['avg_placement'] = trait_statistics[trait]['sum_placements']/trait_statistics[trait]['games']
                    trait_statistics[trait]['top_4_rate'] = trait_statistics[trait]['top_4_count']/trait_statistics[trait]['games']

    for key in temp_comp_statistics:
        if key not in comp_statistics:
            comp_statistics[key] = { 'winrate': 0, 'games': 0, 'avg_placement': 0, 'sum_placements': 0, 'wins': 0, 'top_4_count': 0, 'top_4_rate': 0 }
        temp = temp_comp_statistics.get(key)
        comp = comp_statistics.get(key)

        comp['games'] += temp['games']
        comp['wins'] += temp['wins']
        comp['top_4_count'] += temp['top_4_count']
        comp['sum_placements'] += temp['sum_placements']

        comp['winrate'] = comp['wins']/comp['games']
        comp['avg_placement'] = comp['sum_placements']/comp['games']
        comp['top_4_rate'] = comp['top_4_count']/comp['games']

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
    global trait_set
    unit_set = {""}
    traits = {}
    for unit in comp:
        if unit not in unit_set:
            unit_set.add(unit)
            for trait in trait_set[unit]:
                traits[trait] = traits.get(trait, 0) + 1
    sorted_dict = sorted(traits.items(), key=lambda x: (x[1], x[0]), reverse=True)
    return repr([repr(value) + ' ' + key for key, value in sorted_dict])


if __name__ == "__main__":
    start()
    matchDataStats(MatchData.query.all()) 
    app.run(debug=True)
