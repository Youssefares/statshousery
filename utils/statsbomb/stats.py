from collections import defaultdict
import pandas as pd


def player_90s(substitutions, starting_xis, half_ends):
  player_90s = defaultdict(lambda: 0)  
  
  for index, starting_xi in starting_xis.iterrows():
    for player in starting_xi.lineup:
      player_name = player['player']['name']
      for period in range(1, 3):
        half_end = half_ends[(half_ends.match_id == starting_xi.match_id) & (half_ends.period==period)].iloc[0]
        minutes = half_end.minute + half_end.second/60
        if period == 2:
          minutes -= 45
        match_subs = substitutions[
          (substitutions.match_id == starting_xi.match_id) & (substitutions.player == player_name)
        ]
        if len(match_subs) > 0:
          player_90s[player_name] += (match_subs.iloc[0].minute + match_subs.iloc[0].second/60)/90
          break
        else:
          player_90s[player_name] += minutes/90
    
  for index, substitution in substitutions.iterrows():
    half_end = half_ends[(half_ends.match_id == substitution.match_id) & (half_ends.period==substitution.period)].iloc[0]
    player_90s[substitution.replacement] += (half_end.minute+half_end.second/60-substitution.minute-substitution.second/60)/90
      
  return pd.DataFrame({
      'player': list(player_90s.keys()),
      '90s Played': list(player_90s.values()),
  })

def foul_won_stats(fouls_won):
  return pd.DataFrame({
      'player': fouls_won.player,
      'Penalties Won': fouls_won.penalty.notna().astype(int),
      'Fouls Won': fouls_won.id,
  }).groupby('player', as_index=False).agg({
      'Penalties Won': 'sum',
      'Fouls Won': 'count',
  })

def foul_committed_stats(fouls_committed):
  card_dummies = pd.get_dummies(
      fouls_committed[['card']],
      columns=['card'],
      prefix='',
      prefix_sep='',
  ).T.reindex(['Yellow Card', 'Second Yellow', 'Red Card']).T.fillna(0)

  type_dummies = pd.get_dummies(
      fouls_committed[['type']],
      columns=['type'],
      prefix='',
      prefix_sep='',
  ).T.reindex(['Dive', 'Dangerous Play']).T.fillna(0)

  return pd.DataFrame({
      'player': fouls_committed.player,
      'CounterPress Fouls': fouls_committed.counterpress.notna().astype(int),
      'Fouls Committed': fouls_committed.id,
      'Penalties Conceded': fouls_committed.penalty.notna().astype(int),
      'Yellow Cards':  card_dummies['Yellow Card'],
      'Second Yellows': card_dummies['Second Yellow'],
      'Red Cards': card_dummies['Red Card'],
      'Dives': type_dummies['Dive'],
      'Dangerous Plays': type_dummies['Dangerous Play'],
  }).groupby('player', as_index=False).agg({
      'CounterPress Fouls': 'sum',
      'Fouls Committed': 'count',
      'Penalties Conceded': 'sum',
      'Yellow Cards': 'sum',
      'Second Yellows': 'sum',
      'Red Cards': 'sum',
      'Dives': 'sum',
      'Dangerous Plays': 'sum',
  })

def dribbled_past_stats(dribbled_pasts):
  return dribbled_pasts.groupby('player', as_index=False).agg({
      'id': 'count',
  }).rename(columns={'id': 'Dribbled Past'})

def dispossessed_stats(dispossessed_stats):
  return dispossessed_stats.groupby('player', as_index=False).agg({
      'id': 'count',
  }).rename(columns={'id': 'Dispossessed'})

def shot_stats(shots):
  return pd.get_dummies(
      shots,
      columns=['outcome'],
      prefix='', prefix_sep='',
  ).groupby('player', as_index=False).agg({
      'xG': 'sum',
      'Goal': 'sum',
      'id': 'count',
  }).rename(columns={'id': 'Shots', 'Goal': 'Goals'})

def pass_stats(passes, shots):
  return pd.DataFrame({
      'id': passes.id,
      'Shot Assists': passes.shot_assist,
      'Avg Pass Length': passes.length,
      'Assists': passes.goal_assist,
      'Passes Completed': passes.outcome.isna().astype(int),
      'Assisted Shot Id': passes.assisted_shot_id,
      'player': passes.player,
  }).merge(
      shots[['id', 'xG']],
      'left',
      left_on='Assisted Shot Id',
      right_on='id',
      suffixes=('', '_of_shot')
  ).groupby('player', as_index=False).agg({
    'Passes Completed': 'sum',
    'id': 'count',
    'Avg Pass Length': 'mean',
    'xG': 'sum',
    'Shot Assists': 'count',
    'Assists': 'count',
  }).rename(columns={
      'id': 'Passes Attempted',
      'xG': 'xG Assisted',
  })


def dribble_stats(dribbles):
  return pd.get_dummies(
      dribbles, columns=['outcome'], prefix='', prefix_sep='',
  ).groupby('player', as_index=False).agg({
      'Complete': 'sum',
      'id': 'count'},
  ).rename(columns={
      'Complete': 'Dribbles Completed',
      'id': 'Dribbles Attempted',
  })

def pressure_stats(pressures):
  return pressures.groupby('player', as_index=False).agg({
      'id': 'count',
      'counterpress': 'count'
  }).rename(columns={
      'id': 'Pressures',
      'counterpress': 'CounterPress Pressures',
  })


def player_summary(clean_events, team, player=None, match_id=None, normalize=False, normalize_cols=None):
  team_events = {
      event_type: events[events.team == team] for event_type, events in clean_events.items()
  }
  
  playing_stats = player_90s(
      team_events['substitutions'],
      team_events['starting_xis'],
      team_events['half_ends'],
  )

  stats = f.reduce(lambda df, other: df.merge(other, on='player', how='left'), [
    shot_stats(team_events['shots']),
    pass_stats(team_events['passes'], team_events['shots']),
    dribble_stats(team_events['dribbles']),
    pressure_stats(team_events['pressures']),
    foul_won_stats(team_events['foul_wons']),
    foul_committed_stats(team_events['foul_committeds']),
    dribbled_past_stats(team_events['dribbled_pasts']),
    dispossessed_stats(team_events['dispossesseds'])
  ], playing_stats)

  ratios = {
      'Pass Completion %': stats['Passes Completed']/stats['Passes Attempted']*100,
      'Dribble Completion %': stats['Dribbles Completed']/stats['Dribbles Attempted']*100,
      'xG/Shot': stats['xG']/stats['Shots'],
      'Fouls/Yellow Card': stats['Fouls Committed']/(stats['Yellow Cards'] + stats['Second Yellows']),
  }
  stats_with_ratios = stats.assign(**ratios).rename(columns={
      'player': 'Player',
  })

  if normalize and normalize_cols is None:
    unnormalizable_cols = [
      'Player', '90s Played', 'Avg Pass Length', 
    ] + list(ratios.keys())

    cols = ~stats_with_ratios.columns.isin(unnormalizable_cols)
    stats_with_ratios.loc[:,cols] = stats_with_ratios.loc[:,cols].div(
        stats_with_ratios['90s Played'].values,
        axis=0,
    ) 
  elif normalize:
    # Normalize all columns except ratios
    stats_with_ratios[normalize_cols] = stats_with_ratios[normalize_cols].div(
        stats_with_ratios['90s Played'].values,
        axis=0,
    )
  
  return stats_with_ratios
