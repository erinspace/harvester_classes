from __future__ import unicode_literals

import json

from base import OAIHarvester


texas_harvester = OAIHarvester(
    'texas', 'http://digital.library.txstate.edu/oai/')
texas_harvested = texas_harvester.harvest(days_back=15)
texas_normed = texas_harvester.normalize(
    raw_doc=texas_harvested[0],
    property_list=['date', 'creator', 'language']
)


mit_harvester = OAIHarvester('mit', 'http://dspace.mit.edu/oai/')
mit_harvested = mit_harvester.harvest(days_back=2)
mit_normed = mit_harvester.normalize(
    raw_doc=mit_harvested[0],
    property_list=[
        'identifier', 'type', 'source', 'language', 'relation', 'rights']
)


print(json.dumps(texas_normed.attributes, indent=4))
print(json.dumps(mit_normed.attributes, indent=4))
