#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/mobility-module.h"
#include "ns3/wifi-module.h"
#include "ns3/internet-module.h"
#include "ns3/aodv-module.h"
#include "ns3/applications-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/ipv4-list-routing.h"
#include "ns3/energy-module.h"
#include <fstream>
#include <sstream>
#include <string>

using namespace ns3;

std::ofstream g_traceFile;

static void LogTrustMetrics(NodeContainer nodes, Time interval)
{
    double time = Simulator::Now().GetSeconds();
    for (uint32_t i = 0; i < nodes.GetN(); ++i) {
        Ptr<Node> node = nodes.Get(i);
        Ptr<Ipv4RoutingProtocol> proto = node->GetObject<Ipv4>()->GetRoutingProtocol();
        Ptr<aodv::RoutingProtocol> aodvDirect = DynamicCast<aodv::RoutingProtocol>(proto);
        if (!aodvDirect) {
            Ptr<Ipv4ListRouting> listRouting = DynamicCast<Ipv4ListRouting>(proto);
            if (listRouting) {
                for (uint32_t j = 0; j < listRouting->GetNRoutingProtocols(); ++j) {
                    int16_t priority;
                    Ptr<Ipv4RoutingProtocol> sub = listRouting->GetRoutingProtocol(j, priority);
                    if (DynamicCast<aodv::RoutingProtocol>(sub)) {
                        aodvDirect = DynamicCast<aodv::RoutingProtocol>(sub);
                        break;
                    }
                }
            }
        }
        
        if (aodvDirect) {
            uint32_t rx = aodvDirect->GetPacketsReceived();
            uint32_t fw = aodvDirect->GetPacketsForwarded();
            uint32_t drop = aodvDirect->GetPacketsDropped();
            BooleanValue malVal;
            aodvDirect->GetAttribute("IsMalicious", malVal);
            bool isMalicious = malVal.Get();
            
            if (g_traceFile.is_open()) {
                g_traceFile << time << "," << i << "," << rx << "," << fw << "," << drop << "," << (isMalicious ? 1 : 0) << std::endl;
            }
        }
    }
    Simulator::Schedule(interval, &LogTrustMetrics, nodes, interval);
}

static void ScheduleBlacklist(NodeContainer nodes, uint32_t maliciousNodeId, double atTime)
{
    if (maliciousNodeId >= nodes.GetN()) return;
    Ptr<Node> malNode = nodes.Get(maliciousNodeId);
    Ipv4Address malIp = malNode->GetObject<Ipv4>()->GetAddress(1, 0).GetLocal();
    std::cout << "[TRUST] At time " << atTime << "s, blacklisting node " << maliciousNodeId << " (" << malIp << ")" << std::endl;
    
    // Hard isolation constraint
    Ptr<Ipv4> ipv4 = malNode->GetObject<Ipv4>();
    if (ipv4 && ipv4->GetNInterfaces() > 1) {
        if (ipv4->IsUp(1)) {
            ipv4->SetDown(1);
            std::cout << "[NS3 ROUTING] Node " << maliciousNodeId << " = MALICIOUS" << std::endl;
            std::cout << "[NS3 ROUTING] RREQ forwarding = BLOCKED (Interface Down)" << std::endl;
        } else {
            std::cout << "[NS3 ROUTING] Node " << maliciousNodeId << " interface is already DOWN. Safely ignoring duplicate blacklist request." << std::endl;
        }
    }
    
    for (uint32_t i = 0; i < nodes.GetN(); ++i) {
        if (i == maliciousNodeId) continue;
        Ptr<Node> node = nodes.Get(i);
        Ptr<Ipv4RoutingProtocol> proto = node->GetObject<Ipv4>()->GetRoutingProtocol();
        Ptr<aodv::RoutingProtocol> aodvDirect = DynamicCast<aodv::RoutingProtocol>(proto);
        if (!aodvDirect) {
            Ptr<Ipv4ListRouting> listRouting = DynamicCast<Ipv4ListRouting>(proto);
            if (listRouting) {
                for (uint32_t j = 0; j < listRouting->GetNRoutingProtocols(); ++j) {
                    int16_t priority;
                    Ptr<Ipv4RoutingProtocol> sub = listRouting->GetRoutingProtocol(j, priority);
                    if (DynamicCast<aodv::RoutingProtocol>(sub)) {
                        aodvDirect = DynamicCast<aodv::RoutingProtocol>(sub);
                        break;
                    }
                }
            }
        }
        if (aodvDirect) {
            aodvDirect->BlacklistNode(malIp);
        }
    }
}

static void ApplyLARFilter(NodeContainer nodes, uint32_t srcId, uint32_t dstId, double margin)
{
    if (srcId >= nodes.GetN() || dstId >= nodes.GetN()) return;
    
    Ptr<MobilityModel> srcMob = nodes.Get(srcId)->GetObject<MobilityModel>();
    Ptr<MobilityModel> dstMob = nodes.Get(dstId)->GetObject<MobilityModel>();
    if (!srcMob || !dstMob) return;
    
    Vector pSrc = srcMob->GetPosition();
    Vector pDst = dstMob->GetPosition();
    
    double minX = std::min(pSrc.x, pDst.x) - margin;
    double maxX = std::max(pSrc.x, pDst.x) + margin;
    double minY = std::min(pSrc.y, pDst.y) - margin;
    double maxY = std::max(pSrc.y, pDst.y) + margin;
    
    std::cout << "[LAR] Applying Geographic Request Zone: X[" << minX << ", " << maxX 
              << "] Y[" << minY << ", " << maxY << "]" << std::endl;
              
    for (uint32_t i = 0; i < nodes.GetN(); ++i) {
        if (i == srcId || i == dstId) continue;
        
        Ptr<MobilityModel> mob = nodes.Get(i)->GetObject<MobilityModel>();
        Vector p = mob->GetPosition();
        
        bool outside = (p.x < minX || p.x > maxX || p.y < minY || p.y > maxY);
        if (outside) {
            std::cout << "[LAR] Node " << i << " at (" << p.x << ", " << p.y << ") is OUTSIDE Request Zone. Restricting routing." << std::endl;
            Ipv4Address malIp = nodes.Get(i)->GetObject<Ipv4>()->GetAddress(1, 0).GetLocal();
            // Blacklist this node on all other nodes so its RREQs are ignored
            for (uint32_t j = 0; j < nodes.GetN(); ++j) {
                if (i == j) continue;
                Ptr<Ipv4RoutingProtocol> proto = nodes.Get(j)->GetObject<Ipv4>()->GetRoutingProtocol();
                Ptr<aodv::RoutingProtocol> aodvDirect = DynamicCast<aodv::RoutingProtocol>(proto);
                if (!aodvDirect) {
                    Ptr<Ipv4ListRouting> listRouting = DynamicCast<Ipv4ListRouting>(proto);
                    if (listRouting) {
                        for (uint32_t k = 0; k < listRouting->GetNRoutingProtocols(); ++k) {
                            int16_t priority;
                            Ptr<Ipv4RoutingProtocol> sub = listRouting->GetRoutingProtocol(k, priority);
                            if (DynamicCast<aodv::RoutingProtocol>(sub)) {
                                aodvDirect = DynamicCast<aodv::RoutingProtocol>(sub);
                                break;
                            }
                        }
                    }
                }
                if (aodvDirect) {
                    aodvDirect->BlacklistNode(malIp);
                }
            }
        }
    }
}

NS_LOG_COMPONENT_DEFINE("BasicManetSimulation");

static bool SetNodeMalicious(Ptr<Node> node, uint32_t nodeId)
{
    Ptr<Ipv4> ipv4 = node->GetObject<Ipv4>();
    if (!ipv4) return false;

    // PHYSICALLY ISOLATE THE MALICIOUS NODE
    // Bring down the WiFi interface (Interface 1) so it cannot participate.
    // if (ipv4->GetNInterfaces() > 1) {
    //     ipv4->SetDown(1);
    // }
    std::cout << "[NS3 ROUTING] Node " << nodeId << " = MALICIOUS" << std::endl;
    // std::cout << "[NS3 ROUTING] RREQ forwarding = BLOCKED (Interface Down)" << std::endl;

    Ptr<Ipv4RoutingProtocol> proto = ipv4->GetRoutingProtocol();
    if (!proto) {
        std::cout << "[NS3 DEBUG] Node " << nodeId << " proto is null!" << std::endl;
        return true;
    }

    Ptr<aodv::RoutingProtocol> aodvDirect = DynamicCast<aodv::RoutingProtocol>(proto);
    if (aodvDirect) {
        aodvDirect->SetAttribute("IsMalicious", BooleanValue(true));
        std::cout << "[NS3 DEBUG] Node " << nodeId << " aodvDirect IsMalicious SET TO TRUE!" << std::endl;
        return true;
    }

    Ptr<Ipv4ListRouting> listRouting = DynamicCast<Ipv4ListRouting>(proto);
    if (listRouting) {
        std::cout << "[NS3 DEBUG] Node " << nodeId << " listRouting has " << listRouting->GetNRoutingProtocols() << " protocols" << std::endl;
        for (uint32_t i = 0; i < listRouting->GetNRoutingProtocols(); ++i) {
            int16_t priority;
            Ptr<Ipv4RoutingProtocol> sub = listRouting->GetRoutingProtocol(i, priority);
            Ptr<aodv::RoutingProtocol> aodvSub = DynamicCast<aodv::RoutingProtocol>(sub);
            if (aodvSub) {
                aodvSub->SetAttribute("IsMalicious", BooleanValue(true));
                std::cout << "[NS3 DEBUG] Node " << nodeId << " aodvSub IsMalicious SET TO TRUE!" << std::endl;
                return true;
            }
        }
    }
    std::cout << "[NS3 DEBUG] Node " << nodeId << " NO AODV PROTOCOL FOUND!" << std::endl;
    return true;
}

int main(int argc, char *argv[])
{
    uint32_t nNodes = 8;
    double simulationTime = 60.0;
    std::string maliciousNodes = "";
    std::string outputFile = "manet-flowmon-results.xml";
    std::string traceFile = "";
    std::string routeTraceFile = "";
    std::string trustFile = "";
    std::string energyFile = "energy_results.csv";
    uint32_t rngSeed = 1;
    uint32_t sourceNode = 0;
    uint32_t destNode = 255; // 255 means use nNodes-1

    double simArea = 150.0;

    CommandLine cmd;
    cmd.AddValue("nNodes",         "Number of nodes",             nNodes);
    cmd.AddValue("simulationTime", "Simulation time (s)",         simulationTime);
    cmd.AddValue("maliciousNodes", "Attacker node IDs (CSV)",     maliciousNodes);
    cmd.AddValue("outputFile",     "FlowMonitor XML output",      outputFile);
    cmd.AddValue("traceFile",      "Output CSV trace file",       traceFile);
    cmd.AddValue("routeTraceFile", "Output ASCII routing trace",  routeTraceFile);
    cmd.AddValue("trustFile",      "Input LSTM predictions file", trustFile);
    cmd.AddValue("energyFile",     "Path to save energy results", energyFile);
    cmd.AddValue("RngSeed",        "RNG seed",                    rngSeed);
    cmd.AddValue("sourceNode",     "Source node ID",              sourceNode);
    cmd.AddValue("destNode",       "Destination node ID",         destNode);
    cmd.AddValue("simArea",        "Simulation area",             simArea);
    cmd.Parse(argc, argv);

    if (destNode == 255) {
        destNode = nNodes - 1;
    }

    RngSeedManager::SetSeed(rngSeed);

    std::cout << "Config: nNodes=" << nNodes
              << " simulationTime=" << simulationTime
              << " maliciousNodes=" << maliciousNodes
              << " RngSeed=" << rngSeed
              << " outputFile=" << outputFile << std::endl;

    NodeContainer nodes;
    nodes.Create(nNodes);

    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211b);

    // Dynamically calculate TxPower to ensure transmission range is ~60% of simArea.
    // Default YansWifiPhy ED threshold is ~ -82 dBm.
    // Path loss L = 46.67 + 30 * log10(d).
    double targetRange = simArea * 0.6;
    if (targetRange < 1.0) targetRange = 1.0;
    double pathLoss = 46.67 + 30.0 * std::log10(targetRange);
    double txPower = pathLoss - 82.0;
    
    YansWifiPhyHelper wifiPhy;
    wifiPhy.Set("TxPowerStart", DoubleValue(txPower));
    wifiPhy.Set("TxPowerEnd",   DoubleValue(txPower));

    YansWifiChannelHelper wifiChannel = YansWifiChannelHelper::Default();
    wifiPhy.SetChannel(wifiChannel.Create());

    WifiMacHelper wifiMac;
    wifiMac.SetType("ns3::AdhocWifiMac");

    NetDeviceContainer devices = wifi.Install(wifiPhy, wifiMac, nodes);

    // Setup Energy Model
    BasicEnergySourceHelper basicSourceHelper;
    basicSourceHelper.Set("BasicEnergySourceInitialEnergyJ", DoubleValue(100.0));
    EnergySourceContainer sources = basicSourceHelper.Install(nodes);

    WifiRadioEnergyModelHelper radioEnergyHelper;
    DeviceEnergyModelContainer deviceModels = radioEnergyHelper.Install(devices, sources);

    // Mobility for Relays - scale bounding box to entire simArea to allow LAR filtering
    double minX = 0.0;
    double maxX = simArea;
    double minY = 0.0;
    double maxY = simArea;
    
    MobilityHelper mobilityRelays;
    ObjectFactory pos;
    pos.SetTypeId("ns3::RandomRectanglePositionAllocator");
    std::stringstream ssX, ssY;
    ssX << "ns3::UniformRandomVariable[Min=" << minX << "|Max=" << maxX << "]";
    ssY << "ns3::UniformRandomVariable[Min=" << minY << "|Max=" << maxY << "]";
    pos.Set("X", StringValue(ssX.str()));
    pos.Set("Y", StringValue(ssY.str()));
    Ptr<PositionAllocator> taPositionAlloc = pos.Create()->GetObject<PositionAllocator>();

    mobilityRelays.SetPositionAllocator(taPositionAlloc);
    mobilityRelays.SetMobilityModel("ns3::RandomWaypointMobilityModel",
                              "Speed",             StringValue("ns3::UniformRandomVariable[Min=1.0|Max=5.0]"),
                              "Pause",             StringValue("ns3::ConstantRandomVariable[Constant=2.0]"),
                              "PositionAllocator", PointerValue(taPositionAlloc));

    // Mobility for Source and Destination (Fixed at opposite ends: 0 and 800. Distance = 800m > 250m range)
    MobilityHelper mobilitySrcDst;
    Ptr<ListPositionAllocator> srcDstAlloc = CreateObject<ListPositionAllocator>();
    srcDstAlloc->Add(Vector(0.0, simArea / 2.0, 0.0));       // Source at left
    srcDstAlloc->Add(Vector(simArea, simArea / 2.0, 0.0));   // Dest at right
    mobilitySrcDst.SetPositionAllocator(srcDstAlloc);
    mobilitySrcDst.SetMobilityModel("ns3::ConstantPositionMobilityModel");

    // Install mobility separately
    NodeContainer srcDstNodes;
    srcDstNodes.Add(nodes.Get(sourceNode));
    srcDstNodes.Add(nodes.Get(destNode));

    NodeContainer relayNodes;
    for (uint32_t i = 0; i < nNodes; ++i) {
        if (i != sourceNode && i != destNode) {
            relayNodes.Add(nodes.Get(i));
        }
    }

    mobilitySrcDst.Install(srcDstNodes);
    mobilityRelays.Install(relayNodes);

    // Print Initial Topology
    for (uint32_t i = 0; i < nodes.GetN(); ++i) {
        Ptr<MobilityModel> mob = nodes.Get(i)->GetObject<MobilityModel>();
        Simulator::Schedule(Seconds(2.0), [i, mob]() {
            Vector p = mob->GetPosition();
            std::cout << "[TOPOLOGY] Node " << i << " -> (" << p.x << ", " << p.y << ", " << p.z << ")" << std::endl;
        });
    }


    AodvHelper aodv;
    InternetStackHelper internet;
    internet.SetRoutingHelper(aodv);
    internet.Install(nodes);

    if (!maliciousNodes.empty()) {
        std::vector<uint32_t> parsedMalNodes;
        std::stringstream ss(maliciousNodes);
        std::string item;
        while (std::getline(ss, item, ',')) {
            // Strip any remaining quotes or brackets just in case
            std::string clean_item = "";
            for (char c : item) {
                if (std::isdigit(c)) clean_item += c;
            }
            if (!clean_item.empty()) {
                try {
                    uint32_t m = std::stoul(clean_item);
                    if (m < nNodes) {
                        parsedMalNodes.push_back(m);
                        SetNodeMalicious(nodes.Get(m), m);
                    }
                } catch (const std::exception& e) {
                    std::cerr << "Warning: Invalid malicious node ID '" << item << "'" << std::endl;
                }
            }
        }
        
        std::cout << "[NS3 INPUT]" << std::endl;
        std::cout << "Malicious nodes received = [";
        for (size_t i = 0; i < parsedMalNodes.size(); ++i) {
            std::cout << parsedMalNodes[i] << (i < parsedMalNodes.size() - 1 ? ", " : "");
        }
        std::cout << "]" << std::endl;
    }

    Ipv4AddressHelper ipv4h;
    ipv4h.SetBase("10.1.1.0", "255.255.255.0");
    Ipv4InterfaceContainer interfaces = ipv4h.Assign(devices);

    // Enable ASCII routing trace if requested
    // Captures real IP-layer receive/transmit events per node for hop extraction
    if (!routeTraceFile.empty()) {
        AsciiTraceHelper ascii;
        internet.EnableAsciiIpv4All(ascii.CreateFileStream(routeTraceFile));
        std::cout << "[ROUTE] ASCII routing trace enabled: " << routeTraceFile << std::endl;
    }

    uint16_t port = 9;

    UdpEchoServerHelper server(port);
    ApplicationContainer serverApps = server.Install(nodes.Get(destNode));
    serverApps.Start(Seconds(1.0));
    serverApps.Stop(Seconds(simulationTime - 1.0));

    UdpEchoClientHelper client(interfaces.GetAddress(destNode), port);
    client.SetAttribute("MaxPackets", UintegerValue(100));
    client.SetAttribute("Interval",   TimeValue(Seconds(0.5)));
    client.SetAttribute("PacketSize", UintegerValue(1024));

    ApplicationContainer clientApps = client.Install(nodes.Get(sourceNode));
    clientApps.Start(Seconds(2.0));
    clientApps.Stop(Seconds(simulationTime - 2.0));

    FlowMonitorHelper flowmon;
    Ptr<FlowMonitor> monitor = flowmon.InstallAll();

    if (!traceFile.empty()) {
        g_traceFile.open(traceFile);
        if (g_traceFile.is_open()) {
            g_traceFile << "time,node,rx,fw,drop,label" << std::endl;
            Simulator::Schedule(Seconds(1.0), &LogTrustMetrics, nodes, Seconds(1.0));
        }
    }

    if (!trustFile.empty()) {
        std::ifstream tfile(trustFile);
        if (tfile.is_open()) {
            std::string line;
            // Skip header if any
            std::getline(tfile, line);
            while (std::getline(tfile, line)) {
                std::stringstream ss(line);
                std::string timeStr, nodeStr, scoreStr, isMalStr;
                if (std::getline(ss, timeStr, ',') && 
                    std::getline(ss, nodeStr, ',') && 
                    std::getline(ss, scoreStr, ',') && 
                    std::getline(ss, isMalStr, ',')) {
                    double t = std::stod(timeStr);
                    uint32_t nid = std::stoul(nodeStr);
                    int is_mal = std::stoi(isMalStr);
                    if (is_mal == 1) {
                        Simulator::Schedule(Seconds(t), &ScheduleBlacklist, nodes, nid, t);
                    }
                }
            }
        }
    }

    // Schedule the LAR geographic filter before traffic starts
    // Use a larger margin (simArea * 0.5) so that detours around malicious nodes are not artificially blocked
    Simulator::Schedule(Seconds(1.9), &ApplyLARFilter, nodes, sourceNode, destNode, simArea * 0.5);

    Simulator::Stop(Seconds(simulationTime));
    Simulator::Run();

    monitor->CheckForLostPackets();
    monitor->SerializeToXmlFile(outputFile, true, true);

    if (g_traceFile.is_open()) {
        g_traceFile.close();
    }

    // Output energy results
    std::ofstream energyStream(energyFile.c_str());
    if (energyStream.is_open()) {
        energyStream << "node_id,initial_energy,remaining_energy,consumed_energy,residual_percentage\n";
        for (uint32_t i = 0; i < nodes.GetN(); ++i) {
            Ptr<BasicEnergySource> source = DynamicCast<BasicEnergySource>(sources.Get(i));
            if (source) {
                double initial = source->GetInitialEnergy();
                double remaining = source->GetRemainingEnergy();
                double consumed = initial - remaining;
                double percentage = 0.0;
                if (initial > 0) {
                    percentage = (remaining / initial) * 100.0;
                }
                energyStream << i << "," << initial << "," << remaining << "," 
                             << consumed << "," << percentage << "\n";
            }
        }
        energyStream.close();
    }

    Simulator::Destroy();
    return 0;
}
