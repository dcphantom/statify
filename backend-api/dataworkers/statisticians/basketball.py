from pprint import pprint

from dataworkers.statisticians.statistician import Statistician

# REMOVE LATER
player_keys = ['player id', 'jersey #', 'team', 'full name', 'email', 'position', 'starting?']
pbp_keys = ['play-type', 'quarter', 'minute', 'seconds', 'shooter', 'shot type', 'made shot?', 'assist?', 'assister', 'shooting foul?', 'fouler', 'rebounder', 'block?', 'blocker', 'turnover committer', 'steal?', 'stealer', 'non-shooting fouler', 'subbing in', 'subbing out', 'timeout?', 'timeout team', 'quarter end']

class BasketballStatistician(Statistician):
    def __init__(self, sport):
        super().__init__(sport)
        
    def process_data(self, data):
        players = data['roster']
        pbp = data['pbp']
        self.init_teams(players)
        self.init_roster_map()
        self.process_rosters(players)
        # self.process_play_by_play(pbp)
        # return self.finalize_data({'box-score': 'BOX', 'team-stats': 'TEAM'})

    # MAYBE MOVE TO PARENT CLASS 
    def process_rosters(self, players):
        returning_user_ids = self.process_users(players)
        self.process_teams(returning_user_ids)
        self.process_players(players)
        pprint(self.roster_map)
    
    # NEXT
    def process_play_by_play(self, pbp):
        pbp_props = list(pbp[0].keys())
        for play in pbp:
            # INSERT INTO Query player data into players table of MySQL db
            pprint(play)

    def process_play(self, play):
        if play['play-type'].lower() == 'shooting':
            self.process_scoring(play)

    def process_scoring(self, play):
        # shooter, shot type, made shot?, assist?, assister, shooting foul, fouler, rebounder, # block? blocker
        pass

    def process_turnover(self, play):
        pass

    def process_non_shooting_foul(self, play):
        pass

    def process_sub(self, play):
        pass

    def stoppage(self, play):
        pass