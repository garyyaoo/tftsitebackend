import threading
import json
import requests
from queue import Queue

riot_token = 'RGAPI-dd7a85dc-4e18-41db-b2ee-92691d073cab'
headers={ 'X-Riot-Token': riot_token}

queue = Queue()
match_data = {}
thread = None

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

def visualizeMatchData():
    global match_data
    return match_data.__repr__()

def cancel():
    global thread
    thread.cancel()

def getPlayersInLeague(league: str) -> None:
    global headers
    base_url = 'https://na1.api.riotgames.com'
    endpoint = '/tft/league/v1/{league}'.format(league=league)
    r = requests.get(base_url + endpoint, headers=headers)
    print(r)
    if r.ok:
        print('get league ok')
        v = json.loads(r.text)
        entries = v['entries'][0:5]
        for e in entries:
            queue.put({'request_type': 'get_summoner_info', 'summoner_name': e['summonerName']})

def getSummonerInfo(summoner_name: str) -> None:
    global headers
    base_url = 'https://na1.api.riotgames.com'
    endpoint = '/tft/summoner/v1/summoners/by-name/{summoner_name}'.format(summoner_name=summoner_name)
    r = requests.get(base_url + endpoint, headers=headers)
    if r.ok:
        print('get info ok')
        v = json.loads(r.text)
        queue.put({'request_type': 'get_player_match_history', 'puuid': v['puuid']})

def getPlayerMatchHistory(puuid: str) -> None:
    global headers
    base_url = 'https://americas.api.riotgames.com'
    endpoint = '/tft/match/v1/matches/by-puuid/{puuid}/ids?count={count}'.format(puuid=puuid, count=20)
    r = requests.get(base_url+endpoint, headers=headers)
    if r.ok:
        print('get history ok')
        v = json.loads(r.text)
        for match_id in v:
            queue.put({'request_type': 'get_match_data', 'match_id': match_id })

def getMatchData(match_id: str) -> None:
    global headers, match_data
    base_url = 'https://americas.api.riotgames.com'
    endpoint = '/tft/match/v1/matches/{match_id}'.format(match_id=match_id)
    r = requests.get(base_url + endpoint, headers=headers)
    if r.ok:
        print('get match ok')
        v = json.loads(r.text)
        if not match_id in match_data:
            match_data[match_id] = v['info']
