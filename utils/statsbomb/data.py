import operator
import functools as f
import json
from pkg_resources import resource_filename

def _events_cleaning_map():
   with open(resource_filename(__name__, './events_cleaning_map.json')) as json_map:
       return(json.load(json_map))

def _find(element_path):
    return lambda json: f.reduce(lambda a, b:  a[b] if a and a == a and b in a else None, element_path.split('.'), json)

def format_events(events, details_col, paths):
  details = pd.DataFrame({
     json_field: events[details_col].apply(_find(path)) for json_field, path in paths.items()
  })

  events_without_generic_cols = events.loc[
    :, (events.columns != details_col) & (events.columns != 'type')
  ]

  return pd.concat([events_without_generic_cols, details], axis=1)

def clean_events(events):
  def column_name(event_name):
    if event_name[-3] == 's':
      return event_name[:-2]
    
    if event_name in ['starting_xis', 'tactical_shifts']:
      return 'tactics'

    return event_name[:-1].replace('/', '_')
  
  events_cleaning_map = _events_cleaning_map()
  modify = events_cleaning_map['modify']
  copy_unmodified = events_cleaning_map['copy_unmodified']

  clean_events = {
      event_name: format_events(
          events[event_name],
          column_name(event_name),
          modify[event_name]
      ) for event_name in modify
  }

  clean_events.update({
      event_name: events[event_name] for event_name in copy_unmodified
  })
  return clean_events
