import unittest

# Need a reference to arcpy to prevent error on helper_functions import
# REQUIRES A LOCAL INSTALL OF ArcMap or ArcPro!!
import archook
archook.get_arcpy()
import arcpy


from helper_functions import tryParseDate
from helper_functions import getMostCommonWithTies
from helper_functions import extractParentheticals
from helper_functions import parseAssessmentCriteria
from helper_functions import extractNepaIds


class TestTryParseDate(unittest.TestCase):
    import datetime

    def setUp(self):
        pass
 
    def test_parse_date(self):
        result = datetime.datetime(2012, 1, 1, 0, 0).date()
        self.assertEqual(tryParseDate('1/1/12'), result)
        self.assertEqual(tryParseDate('1/1/2012'), result)
        self.assertEqual(tryParseDate('1-1-2012'), result)
        self.assertEqual(tryParseDate('Jan 1 2012'), result)
        self.assertEqual(tryParseDate('January 1 2012'), result)


class TestGetMostCommonWithTies(unittest.TestCase):
    def setUp(self):
        pass

    def test_most_common(self):
        singles_ties = ['a', 'b', 'c', 'd']
        double_no_tie = ['a', 'b', 'c', 'd', 'a']
        double_ties = ['a', 'b', 'a', 'b']
        
        singles_ties_result = (True, [('a', 1), ('b', 1), ('c', 1), ('d', 1)])
        double_no_tie_result = (False, [('a', 2)])
        double_ties_result = (True, [('a', 2), ('b', 2)])

        self.assertEqual(getMostCommonWithTies(singles_ties), singles_ties_result)
        self.assertEqual(getMostCommonWithTies(double_no_tie), double_no_tie_result)
        self.assertEqual(getMostCommonWithTies(double_ties), double_ties_result)


class TestExtractParentheticals(unittest.TestCase):
    def setUp(self):
        pass

    def testExtract(self):
        single_paren = 'This is a lame test (or is it?!)'
        double_paren = 'This is a weird way (to) (store text..)'
        nested_paren = 'Now we are really (in the (weeds))'

        single_paren_result = ('This is a lame test (or is it?!)', ['(or is it?!)'])
        double_paren_result = ('This is a weird way (to) (store text..)', ['(to)', '(store text..)'])
        nested_paren_result = ('Now we are really (in the (weeds))', ['(in the (weeds))'])
        
        self.assertEqual(extractParentheticals(single_paren), single_paren_result)
        self.assertEqual(extractParentheticals(double_paren), double_paren_result)
        self.assertEqual(extractParentheticals(nested_paren), nested_paren_result)


class TestParseAssessmentCriteria(unittest.TestCase):
    def setUp(self):
        pass

    def testParseCriteria(self):
        tests = {
            ('Yes', 'No', 'No', 'No') : 'Eligible A Only',
            ('No', 'Yes', 'No', 'No') : 'Eligible B Only',
            ('No', 'No', 'Yes', 'No') : 'Eligible C Only',
            ('No', 'No', 'No', 'Yes') : 'Eligible D Only',
            ('Yes', 'Yes', 'No', 'No') : 'Eligible (A, B, and/or C)',
            ('Yes', 'No', 'Yes', 'No') : 'Eligible (A, B, and/or C)',
            ('Yes', 'No', 'No', 'Yes') : 'Eligible ((A, B and/or C) and D)',
            ('No', 'Yes', 'Yes', 'No') : 'Eligible (A, B, and/or C)',
            ('No', 'Yes', 'No', 'Yes') : 'Eligible ((A, B and/or C) and D)',
            ('No', 'No', 'Yes', 'Yes') : 'Eligible ((A, B and/or C) and D)',
            ('Yes', 'Yes', 'Yes', 'No') : 'Eligible (A, B, and/or C)',
            ('Yes', 'Yes', 'No', 'Yes') : 'Eligible ((A, B and/or C) and D)',
            ('No', 'Yes', 'Yes', 'Yes') : 'Eligible ((A, B and/or C) and D)',
            ('No', 'No', 'No', 'No') : 'Not Specified',
            }
        for test_value, test_result in tests.iteritems():
            self.assertEqual(parseAssessmentCriteria(test_value), test_result)


class TestExtractNepaIds(unittest.TestCase):
    def setUp(self):
        pass

    def testExtractNepa(self):
        # DOI-BLM-CO-F(digits, maybe oO)-date-seq type
        nepa_tests = {
            'Blah, blah, DOI-BLM-CO-F020-2012-0039 CX, blah, blah': ['DOI-BLM-CO-F020-2012-0039 CX'],
            'Blah, blah, DOI-BLM-CO-F020-2012-39 DNA, blah, blah': ['DOI-BLM-CO-F020-2012-39 DNA'],
            'Blah, blah, DOI-BLM-CO-F020-12-039 EA, blah, blah': ['DOI-BLM-CO-F020-12-039 EA'],
            'Blah, blah, DOI-BLM-CO-FO20-2012-0039 CX, blah, blah': ['DOI-BLM-CO-FO20-2012-0039 CX'],
            'Blah, blah, DOI-BLM-CO-FO200-12-0039 CX, blah, blah': ['DOI-BLM-CO-FO200-12-0039 CX'],
        }
        for test_value, test_result in nepa_tests.iteritems():
            self.assertEqual(extractNepaIds(test_value), test_result)


if __name__ == '__main__':
    unittest.main()