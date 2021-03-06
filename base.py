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

    def harvest(self, days_back=1):
        pass

    def get_records(self, url):
        pass

    def normalize(self, raw_doc, property_list):
        pass


class OAIHarvester(BaseHarvester):

    NAMESPACES = {'dc': 'http://purl.org/dc/elements/1.1/',
                  'oai_dc': 'http://www.openarchives.org/OAI/2.0/',
                  'ns0': 'http://www.openarchives.org/OAI/2.0/'}

    RECORDS_URL = 'request?verb=ListRecords'

    META_PREFIX_DATE = '&metadataPrefix=oai_dc&from={}'

    RESUMPTION = '&resumptionToken='

    DEFAULT_ENCODING = 'UTF-8'

    record_encoding = None

    def __init__(self, name, base_url):
        self.name = name
        self.base_url = base_url

    def copy_to_unicode(self, element):

        encoding = self.record_encoding or self.DEFAULT_ENCODING
        element = ''.join(element)
        if isinstance(element, unicode):
            return element
        else:
            return unicode(element, encoding=encoding)

    def harvest(self, days_back):

        start_date = str(date.today() - timedelta(int(days_back)))

        records_url = self.base_url + self.RECORDS_URL
        initial_request_url = records_url + \
            self.META_PREFIX_DATE.format(start_date)

        records = self.get_records(initial_request_url, start_date)

        rawdoc_list = []
        for record in records:
            doc_id = record.xpath(
                'ns0:header/ns0:identifier', namespaces=self.NAMESPACES)[0].text
            record = etree.tostring(record, encoding=self.record_encoding)
            rawdoc_list.append(RawDocument({
                'doc': record,
                'source': self.name,
                'docID': self.copy_to_unicode(doc_id),
                'filetype': 'xml'
            }))

        return rawdoc_list

    def get_records(self, url, start_date, resump_token=''):

        data = requests.get(url)
        doc = etree.XML(data.content)
        records = doc.xpath('//ns0:record', namespaces=self.NAMESPACES)
        token = doc.xpath(
            '//ns0:resumptionToken/node()', namespaces=self.NAMESPACES)
        if len(token) == 1:
            time.sleep(0.5)
            base_url = url.replace(
                self.META_PREFIX_DATE.format(start_date), '')
            base_url = base_url.replace(self.RESUMPTION + resump_token, '')
            url = base_url + self.RESUMPTION + token[0]
            records += self.get_records(url, start_date, resump_token=token[0])

        return records

    def get_contributors(self, result):
        ''' this grabs all of the fields marked contributors
        or creators in the OAI namespaces'''

        contributors = result.xpath(
            '//dc:contributor/node()', namespaces=self.NAMESPACES) or ['']
        creators = result.xpath(
            '//dc:creator/node()', namespaces=self.NAMESPACES) or ['']

        all_contributors = contributors + creators

        contributor_list = []
        for person in all_contributors:
            if person:
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

    def get_tags(self, result):
        tags = result.xpath('//dc:subject/node()', namespaces=self.NAMESPACES)
        
        for tag in tags:
            if ', ' in tag:
                tags.remove(tag)
                tags += tag.split(',')

        return [self.copy_to_unicode(tag.lower().strip()) for tag in tags]


    def get_ids(self, result, doc):
        serviceID = doc.get('docID')
        identifiers = result.xpath(
            '//dc:identifier/node()', namespaces=self.NAMESPACES)
        url = ''
        doi = ''
        for item in identifiers:
            if 'doi' in item or 'DOI' in item:
                doi = item
                doi = doi.replace('doi:', '')
                doi = doi.replace('DOI:', '')
                doi = doi.replace('http://dx.doi.org/', '')
                doi = doi.strip(' ')
            if 'http://' in item or 'https://' in item:
                url = item

        return {'serviceID': serviceID, 'url': self.copy_to_unicode(url), 'doi': self.copy_to_unicode(doi)}

    def get_properties(self, result, property_list):
        ''' kwargs can be all of the properties in your particular
        OAI harvester that does not fit into the standard schema '''

        properties = {}
        for item in property_list:
            prop = (
                result.xpath('//dc:{}/node()'.format(item), namespaces=self.NAMESPACES) or [''])

            if len(prop) > 1:
                properties[item] = prop
            else:
                properties[item] = prop[0]

        return properties

    def get_date_created(self, result):
        dates = (
            result.xpath('//dc:date/node()', namespaces=self.NAMESPACES) or [''])
        date = self.copy_to_unicode(dates[0])
        return date

    def get_date_updated(self, result):
        dateupdated = result.xpath(
            '//ns0:header/ns0:datestamp/node()', namespaces=self.NAMESPACES)[0]
        date_updated = parse(dateupdated).isoformat()
        return self.copy_to_unicode(date_updated)

    def get_title(self, result):
        title = result.xpath(
            '//dc:title/node()', namespaces=self.NAMESPACES)[0]
        return self.copy_to_unicode(title)

    def get_description(self, result):
        description = (result.xpath('//dc:description/node()', namespaces=self.NAMESPACES) or [''])[0]
        return self.copy_to_unicode(description)

    def normalize(self, raw_doc, property_list):
        str_result = raw_doc.get('doc')
        result = etree.XML(str_result)

        # TODO : add series names filtering support
        payload = {
            'source': self.name,
            'title': self.get_title(result),
            'description': self.get_description(result),
            'id': self.get_ids(result, raw_doc),
            'contributors': self.get_contributors(result),
            'tags': self.get_tags(result),
            'properties': self.get_properties(result, property_list),
            'dateUpdated': self.get_date_updated(result),
            'dateCreated': self.get_date_created(result)
        }

        return NormalizedDocument(payload)
