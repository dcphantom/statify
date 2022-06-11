from pprint import pprint

from dataworkers.statisticians.game import Game
from dataworkers.statisticians.dataclerk import DataClerk

class Statistician:
    periods = period_length = None # These should be defined on the child class inheriting this parent class
    
    def __init__(self, sport):
        self.game = Game()
        self.sport = sport
        self.data_clerk = DataClerk(sport)
        self.init_sport_id()
        self.init_position_map()

    def init_sport_id(self):
        select_query_args = {
            'SELECT': ['id'],
            "FROM": 'sports',
            "WHERE": f"sport_name = '{self.sport}'"
        }
        query_data = self.data_clerk.query_database('SELECT', select_query_args)
        self.sport_id = query_data['records'][0][0] if query_data['records'] else None
    
    def init_position_map(self):
        select_query_args = {
            'SELECT': ['id', 'position'],
            "FROM": 'positions',
            "WHERE": f'sport_id = {self.sport_id}'
        }
        query_data = self.data_clerk.query_database('SELECT', select_query_args)
        records = query_data['records']
        self.position_map = {position: position_id for position_id, position in records}

    def receive_data(self, data):
        self.data = data
        self.init_teams(self.data['roster'])
        self.init_roster_map()

    def init_teams(self, players):
        teams = set()
        for player in players:
            teams.add(player['team'])
        self.game.start_game(teams, self.periods, self.period_length)

    def init_roster_map(self):
        self.roster_map = {
            team: {
                'team_id': None,
                "players": {},
                "in_game": set(),
                'gamelog_ids': set()
            } for team in self.game.get_teams()
        }

    def process_data(self):
        self.process_rosters(self.data['roster'])
        self.process_play_by_play(self.data['pbp'])
        return self.get_stats()

    def process_rosters(self, players):
        returning_user_ids = self.process_users(players)
        self.process_teams(returning_user_ids)
        self.process_players(players)
        for team in self.roster_map:
            self.game.connect_lineup(team, self.roster_map[team]["in_game"])

    def process_users(self, players):
        returning_user_ids = []
        for player in players:
            player_team = player['team']
            names = player['full name'].split(' ')
            email = player['email']

            user_select_query_args = {
                'SELECT': ['id'],
                "FROM": 'users',
                "WHERE": f"email = '{email}'"
            }
            user_id = self.data_clerk.does_record_exist(user_select_query_args)
            if user_id:
                returning_user_ids.append(user_id)
            else:
                user_entry = {
                    'first_name': names[0],
                    'middle_name': ' '.join(names[1:-1]) if len(names) > 2 else None,
                    'last_name': names[-1],
                    'email': email
                }
                user_id = self.data_clerk.insert_into_db('users', user_entry)
            
            p_input_id = player['player id']
            self.roster_map[player_team]['players'][p_input_id] = {
                "user_id": user_id, 
                "full_name": player['full name']
            }
        return returning_user_ids

    def process_teams(self, returning_user_ids):
        self.find_existing_teams(returning_user_ids)
        self.add_new_teams()
        self.create_game_record()

    def find_existing_teams(self, existing_user_ids):
        if not existing_user_ids:
            return 
            
        user_ids_string = self.data_clerk.format_input_list(existing_user_ids)
        team_names_string = self.data_clerk.format_input_list(self.roster_map)
        where_condition = f'user_id IN ({user_ids_string}) AND team_name IN ({team_names_string})'
        join_select_args = {
            'SELECT': ['team_id', 'team_name', 'COUNT(team_id) AS player_count'],
            "FROM": 'players',
            "JOIN": [
                ["INNER", 'teams', 'teams.id = players.team_id']
            ],
            "WHERE": where_condition,
            "GROUP BY": ['team_id'],
            "ORDER BY": ["player_count"],
            "LIMIT": {
                "count": len(self.roster_map),
                "offset": 0
            },
        } 
        query_data = self.data_clerk.query_database('SELECT', join_select_args)
        if query_data['records']:
            for team_id, team_name, _ in query_data['records']:
                self.roster_map[team_name]['team_id'] = team_id

    def add_new_teams(self):
        for team in self.roster_map:
            if not self.roster_map[team]['team_id']:
                team_entry = {
                    'team_name': team,
                    'league_id': None,
                    'sport_id': self.sport_id
                }
                team_id = self.data_clerk.insert_into_db('teams', team_entry)
                self.roster_map[team]['team_id'] = team_id

    def add_play_to_db(self, play_map):
        play_entry = {
            "game_id": self.game.get_game_id(),
            "score": self.get_current_score(),
            "period": play_map['quarter'],
            "minute": play_map['minute'],
            "second": play_map['second'],
            "team_name": play_map['team'],
            "play_string": play_map['play_string']
        }
        self.data_clerk.insert_into_db('plays', play_entry)

    def process_players(self, players):
        for player in players:
            player_team = player['team']
            player_team_id = self.roster_map[player_team]['team_id']
            p_input_id = player['player id']
            user_id = self.roster_map[player_team]['players'][p_input_id]['user_id']
            player_select_query_args = {
                'SELECT': ['id'],
                "FROM": 'players',
                "WHERE": f"user_id = {user_id} AND team_id = {player_team_id}"
            }
            player_id = self.data_clerk.does_record_exist(player_select_query_args)
            if not player_id:
                player_entry = {
                    "user_id": user_id,
                    "team_id": player_team_id
                }
                player_id = self.data_clerk.insert_into_db('players', player_entry)
                
            position_id = self.process_position(player['position'])
            player_position_id = self.process_player_position(player_id, position_id)

            self.roster_map[player_team]['players'][p_input_id]['player_id'] = player_id
            gamelog_id = self.data_clerk.insert_into_db(
                self.gamelog_table, 
                {'jersey_number': player['jersey #']}
            )
            self.roster_map[player_team]['players'][p_input_id]['gamelog_id'] = gamelog_id
            self.create_performance_record(player_id, gamelog_id, player_position_id)
            
            self.roster_map[player_team]['gamelog_ids'].add(gamelog_id)
            if player['starting?']:
                self.roster_map[player_team]['in_game'].add(gamelog_id)

    def process_position(self, position):
        if position in self.position_map:
            return self.position_map[position]
        
        position_entry = {
            "position": position,
            "sport_id": self.sport_id
        }
        return self.data_clerk.insert_into_db('positions', position_entry)
    
    def process_player_position(self, player_id, position_id):
        table_name = 'player_positions'
        player_position_select_query_args = {
            'SELECT': ['*'],
            "FROM": table_name,
            "WHERE": f'player_id = {player_id} AND position_id = {position_id}'
        } 
        player_position_id = self.data_clerk.does_record_exist(player_position_select_query_args)
        if not player_position_id:
            player_position_entry = {
                "player_id": player_id,
                "position_id": position_id
            }
            player_position_id = self.data_clerk.insert_into_db(table_name, player_position_entry)
        return player_position_id

    def create_game_record(self):
        team_ids = []
        for i, team in enumerate(self.game.get_teams()):
            team_ids.append(self.roster_map[team]['team_id'])
            self.roster_map[team]['team_number'] = i + 1
        game_entry = {f"team{i + 1}_id": tid for i, tid in enumerate(team_ids)}
        game_id = self.data_clerk.insert_into_db('games', game_entry)
        if game_id:
            self.game.set_game_id(game_id)
    
    def create_performance_record(self, player_id, gamelog_id, player_position_id):
        performance_entry = {
            'game_id': self.game.get_game_id(),
            'player_id': player_id,
            'gamelog_id': gamelog_id,
            'player_position_id': player_position_id
        }
        return self.data_clerk.insert_into_db('performances', performance_entry)

    def get_current_score(self):
        select_query_args = {
            'SELECT': [f'team{i + 1}_score' for i in range(len(self.roster_map))],
            "FROM": 'games',
            "WHERE": f"id = '{self.game.get_game_id()}'"
        }
        score_record = self.data_clerk.query_database('SELECT', select_query_args)['records'][0]
        return ':'.join([str(score) for score in score_record])

    def get_team_number(self, player_gamelog_id):
        for team in self.roster_map:
            if player_gamelog_id in self.roster_map[team]['gamelog_ids']:
                return self.roster_map[team]['team_number']

    def get_stats(self):
        stats = {
            'box_score': self.get_box_score(),
            'team_stats': self.get_team_stats(),
            'pbp': self.get_pbp()
        }
        return stats

    def get_pbp(self):
        select_query_args = {
            'SELECT': ['*'],
            "FROM": 'plays',
            "WHERE": f"game_id = {self.game.get_game_id()}",
            "ORDER BY": self.pbp_order_by
        }
        return self.data_clerk.select(select_query_args)

    def process_play_by_play(self, pbp):
        for play in pbp:
            self.process_play(play)

    # Implement this method in any children classes that inherit this class
    def process_play(self, play):
        raise Exception ("Not Implemented")
    