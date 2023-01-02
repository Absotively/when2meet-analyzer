# To make an availability data file, open the when2meet page, and in the Firefox dev tools console type:
#   [PeopleNames,PeopleIDs,TimeOfSlot,AvailableAtSlot]
# Then right-click the Array and click "Copy Object", and paste it into a text file.
# Probably this would also work in Chrome or whatever.

# Each line of the people categorization file should be a person's name, a tab, and then a
# a category name

import argparse
import csv
from dataclasses import dataclass
import datetime
import json
import pathlib
import re
import sys

@dataclass
class Person:
  name: str
  category: str

@dataclass
class Timeslot:
  time: datetime.datetime
  availablePeople: set[int]

@dataclass
class FoundTime:
  startTime: datetime.datetime
  length: datetime.timedelta
  availablePeople: list[str]
  availablePeopleByCategory: dict[str,list[str]]

slotLength = datetime.timedelta(minutes=15)

def process(peopleByID, timeslotsByTime, minimum_time, minimum_people):
  times_found = []
  times_to_skip = set() # we expect timeslotsByTime to be in order
  people_categories_used = set()
  for (timestamp, timeslot) in timeslotsByTime.items():
    if timestamp in times_to_skip:
      continue
    if len(timeslot.availablePeople) < minimum_people:
      continue
    length = slotLength
    nextSlotTimestamp = timestamp + slotLength.total_seconds()
    while nextSlotTimestamp in timeslotsByTime:
      nextSlot = timeslotsByTime[nextSlotTimestamp]
      if nextSlot.availablePeople.issuperset(timeslot.availablePeople):
        length += slotLength
        if (len(nextSlot.availablePeople) == len(timeslot.availablePeople)):
          times_to_skip.add(nextSlotTimestamp)
        nextSlotTimestamp += slotLength.total_seconds()
      else:
        break
    if length < minimum_time:
      continue
    
    time_found = FoundTime(timeslot.time, length, [], {})
    for id in timeslot.availablePeople:
      person = peopleByID[id]
      time_found.availablePeople.append(person.name)
      if person.category:
        if person.category not in time_found.availablePeopleByCategory:
          time_found.availablePeopleByCategory[person.category] = []
        time_found.availablePeopleByCategory[person.category].append(person.name)
        people_categories_used.add(person.category)
        
    times_found.append(time_found)  
    
  return {'times': times_found, 'categories': people_categories_used}
  
def make_csv(times_found, categories, output_file):
  writer = csv.writer(output_file)
  headings = ["timestamp", "start", "end", "length", "people"]
  for category in categories:
    headings.append(category)
   
  writer.writerow(headings)

  for time in times_found:
    details = []
    timestamp = int(time.startTime.timestamp())
    details.append(f'<t:{timestamp}:F>')
    details.append(time.startTime.ctime())
    details.append((time.startTime + time.length).ctime())
    hours = int(time.length / datetime.timedelta(hours=1))
    minutes = int((time.length - datetime.timedelta(hours=hours)) / datetime.timedelta(minutes=1))
    details.append(f'{hours}:{minutes:02}')
    if len(categories) == 0:
      count = len(time.availablePeople)
      nameList = ', '.join(time.avialablePeople)
      details.append(f'{count} ({nameList})')
    else:
      details.append(str(len(time.availablePeople)))
    for category in categories:
      if category in time.availablePeopleByCategory:
        count = len(time.availablePeopleByCategory[category])
        nameList = ', '.join(time.availablePeopleByCategory[category])
        details.append(f'{count} ({nameList})')
      else:
        details.append('0')
   
    writer.writerow(details)


if __name__ == '__main__':
  parser = argparse.ArgumentParser(prog = 'when2meet analyzer')
  parser.add_argument('datafile', type=pathlib.Path)
  parser.add_argument('mintime', help='minimum timeslot lenght, hh:mm')
  parser.add_argument('-p', '--people', type=int, help='minimum available people count')
  parser.add_argument('-c', '--categories', type=pathlib.Path, help='people categorization file')
  parser.add_argument('-o', '--output', type=pathlib.Path, help='output file name')
  
  args = parser.parse_args()
  
  timeComponents = args.mintime.split(':')
  minTime = datetime.timedelta(hours=int(timeComponents[0]), minutes=int(timeComponents[1]))
  
  with open(args.datafile) as availFile:
    w2mdata = json.load(availFile)

  peopleCategories = {}
  if args.categories:
    with open(args.categories) as categoriesFile:
      for line in categoriesFile.readlines():
        catData = line.split('\t')
        peopleCategories[catData[0]] = catData[1].strip()
  
  people = {}
  for i in range(len(w2mdata[0])):
    name = w2mdata[0][i]
    id = w2mdata[1][i]
    if name in peopleCategories:
      people[id] = Person(name, peopleCategories[name])
    else:
      people[id] = Person(name, '')
      
  timeslots = {}
  for i in range(len(w2mdata[2])):
    timestamp = w2mdata[2][i]
    time = datetime.datetime.fromtimestamp(timestamp)
    availablePeople = w2mdata[3][i]
    timeslots[timestamp] = Timeslot(time, set(availablePeople))
    
  if args.people:
    minPeople = args.people
  else:
    minPeople = len(people)
  
  times_found = process(people, timeslots, minTime, minPeople)
  
  if args.output:
    with open(args.output, 'w', newline='') as file:
      make_csv(times_found['times'], times_found['categories'], file)
  else:
    make_csv(times_found['times'], times_found['categories'], sys.stdout)