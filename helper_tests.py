import unittest

# Need a reference to arcpy for offline testing
# REQUIRES A LOCAL INSTALL OF ArcMap or ArcPro!!
import archook
archook.get_arcpy()
import arcpy


from helper_functions import tryParseDate
from helper_functions import getMostCommonWithTies
from helper_functions import replaceAll
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



if __name__ == '__main__':
    unittest.main()