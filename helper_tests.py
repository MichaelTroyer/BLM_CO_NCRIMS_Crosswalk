import unittest

# Need a reference to arcpy for offline testing
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


# class TestGetMostCommonWithTies(unittest.TestCase):

#     def setUp(self):
#         pass

if __name__ == '__main__':
    unittest.main()