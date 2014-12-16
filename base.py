# Classes for scrAPI Harvesters
from __future__ import unicode_literals

import os
import time
from dateutil.parser import parse
from datetime import date, timedelta, datetime

import requests

from lxml import etree

from nameparser import HumanName

from scrapi.linter import lint
from scrapi.linter.document import RawDocument, NormalizedDocument


class BaseHarvester(object):

    def harvest(self, url, days_back=1, **kwargs):
        pass

    def normalize(self, raw_doc, **kwargs):
        pass


class OAIHarvester(BaseHarvester):

    NAMESPACES = {'dc': 'http://purl.org/dc/elements/1.1/',
                    'oai_dc': 'http://www.openarchives.org/OAI/2.0/',
                    'ns0': 'http://www.openarchives.org/OAI/2.0/'}

    def get_records(self, url):
        data = requests.get(url)
        doc = etree.XML(data.content)
        records = doc.xpath('//ns0:record', namespaces=NAMESPACES)
        token = doc.xpath('//ns0:resumptionToken/node()', namespaces=NAMESPACES)

        if len(token) == 1:
            time.sleep(0.5)
            base_url = OAI_DC_BASE_URL + '&resumptionToken='
            url = base_url + token[0]
            records += get_records(url)

        return records


    def getcontributors(result):
        ''' this grabs all of the fields marked contributors
        or creators in the OAI namespaces'''

        contributors = result.xpath(
            '//dc:contributor/node()', namespaces=NAMESPACES) or ['']
        creators = result.xpath(
            '//dc:creator/node()', namespaces=NAMESPACES) or ['']

        all_contributors = contributors + creators

        contributor_list = []
        for person in all_contributors:
            name = HumanName(person)
            contributor = {
                'prefix': name.title,
                'given': name.first,
                'middle': name.middle,
                'family': name.last,
                'suffix': name.suffix,
                'email': '',
                'ORCID': ''
            }
            contributor_list.append(contributor)

        return contributor_list


    def gettags(result):
        tags = result.xpath('//dc:subject/node()', namespaces=NAMESPACES) or []
        return [copy_to_unicode(tag.lower()) for tag in tags]


    def get_ids(result, doc):
        serviceID = doc.get('docID')
        identifiers = result.xpath('//dc:identifier/node()', namespaces=NAMESPACES)
        url = ''
        doi = ''
        for item in identifiers:
            if 'digital.library.txstate.edu' in item or 'hdl.handle.net' in item:
                url = item
            if 'doi' in item or 'DOI' in item:
                doi = item
                doi = doi.replace('doi:', '')
                doi = doi.replace('DOI:', '')
                doi = doi.replace('http://dx.doi.org/', '')
                doi = doi.strip(' ')

        return {'serviceID': serviceID, 'url': copy_to_unicode(url), 'doi': copy_to_unicode(doi)}


    def get_properties(result, **kwargs):
        ''' kwargs can be all of the properties in your particular
        OAI harvester that does not fit into the standard schema '''

        

        result_type = (result.xpath('//dc:type/node()', namespaces=NAMESPACES) or [''])[0]
        rights = result.xpath('//dc:rights/node()', namespaces=NAMESPACES) or ['']
        if len(rights) > 1:
            copyright = ' '.join(rights)
        else:
            copyright = rights
        publisher = (result.xpath('//dc:publisher/node()', namespaces=NAMESPACES) or [''])[0]
        relation = (result.xpath('//dc:relation/node()', namespaces=NAMESPACES) or [''])[0]
        language = (result.xpath('//dc:language/node()', namespaces=NAMESPACES) or [''])[0]
        dates = result.xpath('//dc:date/node()', namespaces=NAMESPACES) or ['']
        set_spec = result.xpath('ns0:header/ns0:setSpec/node()', namespaces=NAMESPACES)[0]
        properties = {
            'type': copy_to_unicode(result_type),
            'dates': copy_to_unicode(dates),
            'language': copy_to_unicode(language),
            'relation': copy_to_unicode(relation),
            'publisherInfo': {
                'publisher': copy_to_unicode(publisher),
            },
            'permissions': {
                'copyrightStatement': copy_to_unicode(copyright),
            }
        }
        return properties


    def get_date_created(result):
        dates = (result.xpath('//dc:date/node()', namespaces=NAMESPACES) or [''])
        date = copy_to_unicode(dates[0])
        return date


    def get_date_updated(result):
        dateupdated = result.xpath('//ns0:header/ns0:datestamp/node()', namespaces=NAMESPACES)[0]
        date_updated = parse(dateupdated).isoformat()
        return copy_to_unicode(date_updated)
