#!/bin/bash

pushd .
cd QASRL-full

mkdir newswire
mkdir wiki

pushd .
cd newswire
wget https://dada.cs.washington.edu/qasrl/data/newswire_nosent.train.qa
wget https://dada.cs.washington.edu/qasrl/data/newswire_nosent.dev.qa
wget https://dada.cs.washington.edu/qasrl/data/newswire_nosent.test.qa
popd

pushd .
cd wiki
wget https://dada.cs.washington.edu/qasrl/data/wiki1.train.qa
wget https://dada.cs.washington.edu/qasrl/data/wiki1.dev.qa
wget https://dada.cs.washington.edu/qasrl/data/wiki1.test.qa
popd

popd