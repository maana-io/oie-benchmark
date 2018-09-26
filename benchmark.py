''' 
Usage:
   benchmark --gold=GOLD_OIE --out=OUTPUT_FILE (--stanford=STANFORD_OIE | --ollie=OLLIE_OIE |--reverb=REVERB_OIE | --clausie=CLAUSIE_OIE | --openiefour=OPENIEFOUR_OIE | --props=PROPS_OIE)

Options:
  --gold=GOLD_OIE              The gold reference Open IE file (by default, it should be under ./oie_corpus/all.oie).
  --out-OUTPUT_FILE            The output file, into which the precision recall curve will be written.
  --clausie=CLAUSIE_OIE        Read ClausIE format from file CLAUSIE_OIE.
  --ollie=OLLIE_OIE            Read OLLIE format from file OLLIE_OIE.
  --openiefour=OPENIEFOUR_OIE  Read Open IE 4 format from file OPENIEFOUR_OIE.
  --props=PROPS_OIE            Read PropS format from file PROPS_OIE
  --reverb=REVERB_OIE          Read ReVerb format from file REVERB_OIE
  --stanford=STANFORD_OIE      Read Stanford format from file STANFORD_OIE
'''
import docopt
import string
import numpy as np
from sklearn.metrics import precision_recall_curve
import re
import logging
logging.basicConfig(level = logging.INFO)

from oie_readers.stanfordReader import StanfordReader
from oie_readers.ollieReader import OllieReader
from oie_readers.reVerbReader import ReVerbReader
from oie_readers.clausieReader import ClausieReader
from oie_readers.openieFourReader import OpenieFourReader
from oie_readers.propsReader import PropSReader

from oie_readers.goldReader import GoldReader
from matcher import Matcher
import csv

class Benchmark:
    ''' Compare the gold OIE dataset against a predicted equivalent '''
    def __init__(self, gold_fn):
        ''' Load gold Open IE, this will serve to compare against using the compare function '''
        gr = GoldReader() 
        gr.read(gold_fn)
        self.gold = gr.oie

    def compare(self, predicted, matchingFunc, output_fn):
        ''' Compare gold against predicted using a specified matching function. 
            Outputs PR curve to output_fn '''
        
        y_true = []
        y_scores = []
        
        truePositives = []
        falsePositives = []
        falseNegatives = []
        
        correctTotal = 0
        unmatchedCount = 0        
        predicted = Benchmark.normalizeDict(predicted)
        gold = Benchmark.normalizeDict(self.gold)
                
        for sent, goldExtractions in gold.items():
            if sent not in predicted:
                # The extractor didn't find any extractions for this sentence
                for goldEx in goldExtractions:   
                    unmatchedCount += len(goldExtractions)
                    for i in goldExtractions :
                        falseNegatives.append(i)
                    correctTotal += len(goldExtractions)
                continue
                
            predictedExtractions = predicted[sent]
            
            for goldEx in goldExtractions:
                correctTotal += 1
                found = False
                
                for predictedEx in predictedExtractions:
                    
                    if output_fn in predictedEx.matched:
                        # This predicted extraction was already matched against a gold extraction
                        # Don't allow to match it again
                        continue
                    
                    if matchingFunc(goldEx, 
                                    predictedEx, 
                                    ignoreStopwords = True, 
                                    ignoreCase = True):
                        print(predictedEx.__dict__)
                        y_true.append(1)
                        y_scores.append(predictedEx.confidence)
                        predictedEx.matched.append(output_fn)
                        truePositives.append(predictedEx)
                        found = True
                        break
                    
                if not found:
                    falseNegatives.append(goldEx)
                    unmatchedCount += 1
                    
            for predictedEx in [x for x in predictedExtractions if (output_fn not in x.matched)]:
                # Add false positives
                y_true.append(0)
                y_scores.append(predictedEx.confidence)
                falsePositives.append(predictedEx)
        
        print('======================false negatives========================')
        tp = []
        for i in truePositives :
            tp.append('{0}\t{1}\t{2}\t{3}\n'.format(i.sent,i.pred,i.args[0],i.args[1]))
        
        fn = []
        for i in falseNegatives :
            print('i',i.sent,i.pred,i.args)
            if(len(i.args)==1):
                i.args.append('')
            
            fn.append('{0}\t{1}\t{2}\t{3}\n'.format(i.sent,i.pred,i.args[0],i.args[1]))

        fp = []
        for i in falsePositives :
            fp.append('{0}\t{1}\t{2}\t{3}\n'.format(i.sent,i.pred,i.args[0],i.args[1]))

        y_true = y_true
        y_scores = y_scores
        
        # recall on y_true, y  (r')_scores computes |covered by extractor| / |True in what's covered by extractor|
        # to get to true recall we do r' * (|True in what's covered by extractor| / |True in gold|) = |true in what's covered| / |true in gold|
        p, r = Benchmark.prCurve(np.array(y_true), np.array(y_scores),
                       recallMultiplier = ((correctTotal - unmatchedCount)/float(correctTotal)))

        print('unmatchedCount',unmatchedCount,'correctTotal',correctTotal, "fn+tp",len(falseNegatives)+len(truePositives),"nm+tp",unmatchedCount+len(truePositives))

        # write PR to file
        with open(output_fn, 'w') as fout:
            fout.write('{0}\t{1}\n'.format("Precision", "Recall"))
            for cur_p, cur_r in sorted(zip(p, r), key = lambda (cur_p, cur_r): cur_r):
                fout.write('{0}\t{1}\n'.format(cur_p, cur_r))

        # write true positive, false positive, false negative data.
        self.writeResult(output_fn+'.tp',tp)
        self.writeResult(output_fn+'.fp',fp)
        self.writeResult(output_fn+'.fn',fn)
    
    @staticmethod
    def writeResult(filename, a):
        # write false positives
        with open(filename, 'w') as fout:
            fout.write('sentence\tpredicate\tsubject\tobject\n')
            for i in a:
                fout.write(i)

    @staticmethod
    def prCurve(y_true, y_scores, recallMultiplier):
        # Recall multiplier - accounts for the percentage examples unreached by 
        precision, recall, _ = precision_recall_curve(y_true, y_scores)
        recall = recall * recallMultiplier
        return precision, recall

    # Helper functions:
    @staticmethod
    def normalizeDict(d):
        return dict([(Benchmark.normalizeKey(k), v) for k, v in d.items()])
    
    @staticmethod
    def normalizeKey(k):
        return Benchmark.removePunct(unicode(Benchmark.PTB_unescape(k.replace(' ','')), errors = 'ignore'))

    @staticmethod
    def PTB_escape(s):
        for u, e in Benchmark.PTB_ESCAPES:
            s = s.replace(u, e)
        return s
    
    @staticmethod
    def PTB_unescape(s):
        for u, e in Benchmark.PTB_ESCAPES:
            s = s.replace(e, u)
        return s
    
    @staticmethod
    def removePunct(s):
        return Benchmark.regex.sub('', s)
    
    # CONSTANTS
    regex = re.compile('[%s]' % re.escape(string.punctuation))
    
    # Penn treebank bracket escapes 
    # Taken from: https://github.com/nlplab/brat/blob/master/server/src/gtbtokenize.py
    PTB_ESCAPES = [('(', '-LRB-'),
                   (')', '-RRB-'),
                   ('[', '-LSB-'),
                   (']', '-RSB-'),
                   ('{', '-LCB-'),
                   ('}', '-RCB-'),]


if __name__ == '__main__':
    args = docopt.docopt(__doc__)
    logging.debug(args)
    
    if args['--stanford']:
        predicted = StanfordReader()
        predicted.read(args['--stanford'])
    
    if args['--props']:
        predicted = PropSReader()
        predicted.read(args['--props'])
       
    if args['--ollie']:
        predicted = OllieReader()
        predicted.read(args['--ollie'])
    
    if args['--reverb']:
        predicted = ReVerbReader()
        predicted.read(args['--reverb'])
    
    if args['--clausie']:
        predicted = ClausieReader()
        predicted.read(args['--clausie'])
        
    if args['--openiefour']:
        predicted = OpenieFourReader()
        predicted.read(args['--openiefour'])

    b = Benchmark(args['--gold'])
    out_filename = args['--out']

    logging.info("Writing PR curve of {} to {}".format(predicted.name, out_filename))
    b.compare(predicted = predicted.oie, 
               matchingFunc = Matcher.lexicalMatch,
               output_fn = out_filename)
    
        
        
