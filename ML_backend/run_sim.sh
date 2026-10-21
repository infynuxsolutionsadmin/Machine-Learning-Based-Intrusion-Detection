#!/bin/bash
cd /home/kumar/MANET/ns-3/ns-allinone-3.41/ns-3.41
./ns3 run 'scratch/manet-sim --nNodes=8 --maliciousNodes="2,5" --simulationTime=5.0 --traceFile=manual_trace.csv'
cat manual_trace.csv
