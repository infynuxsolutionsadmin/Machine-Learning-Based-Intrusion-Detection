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

NS_LOG_COMPONENT_DEFINE("BasicManetSimulation");

static bool SetNodeMalicious(Ptr<Node> node, uint32_t nodeId)
{
    Ptr<Ipv4> ipv4 = node->GetObject<Ipv4>();
    if (!ipv4) return false;

    Ptr<Ipv4RoutingProtocol> proto = ipv4->GetRoutingProtocol();
    if (!proto) return false;

    Ptr<aodv::RoutingProtocol> aodvDirect = DynamicCast<aodv::RoutingProtocol>(proto);
    if (aodvDirect) {
        aodvDirect->SetAttribute("IsMalicious", BooleanValue(true));
        std::cout << "[ATTACK] Node " << nodeId << " configured as BLACK HOLE ATTACKER." << std::endl;
        return true;
    }

    Ptr<Ipv4ListRouting> listRouting = DynamicCast<Ipv4ListRouting>(proto);
    if (listRouting) {
        for (uint32_t i = 0; i < listRouting->GetNRoutingProtocols(); ++i) {
            int16_t priority;
            Ptr<Ipv4RoutingProtocol> sub = listRouting->GetRoutingProtocol(i, priority);
            Ptr<aodv::RoutingProtocol> aodvSub = DynamicCast<aodv::RoutingProtocol>(sub);
            if (aodvSub) {
                aodvSub->SetAttribute("IsMalicious", BooleanValue(true));
                std::cout << "[ATTACK] Node " << nodeId << " configured as BLACK HOLE ATTACKER (list)." << std::endl;
                return true;
            }
        }
    }
    return false;
}

int main(int argc, char *argv[])
{
    uint32_t nNodes = 8;
    double simulationTime = 60.0;
    uint32_t maliciousNode = 255;
    std::string outputFile = "manet-flowmon-results.xml";
    std::string traceFile = "";
    std::string routeTraceFile = "";
    std::string trustFile = "";
    std::string energyFile = "energy_results.csv";
    uint32_t rngSeed = 1;

    CommandLine cmd;
    cmd.AddValue("nNodes",         "Number of nodes",             nNodes);
    cmd.AddValue("simulationTime", "Simulation time (s)",         simulationTime);
    cmd.AddValue("maliciousNode",  "Attacker node ID (255=none)", maliciousNode);
    cmd.AddValue("outputFile",     "FlowMonitor XML output",      outputFile);
    cmd.AddValue("traceFile",      "Output CSV trace file",       traceFile);
    cmd.AddValue("routeTraceFile", "Output ASCII routing trace",  routeTraceFile);
    cmd.AddValue("trustFile",      "Input LSTM predictions file", trustFile);
    cmd.AddValue("energyFile",     "Path to save energy results", energyFile);
    cmd.AddValue("RngSeed",        "RNG seed",                    rngSeed);
    cmd.Parse(argc, argv);

    RngSeedManager::SetSeed(rngSeed);

    std::cout << "Config: nNodes=" << nNodes
              << " simulationTime=" << simulationTime
              << " maliciousNode=" << maliciousNode
              << " RngSeed=" << rngSeed
              << " outputFile=" << outputFile << std::endl;

    NodeContainer nodes;
    nodes.Create(nNodes);

    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211b);

    YansWifiPhyHelper wifiPhy;
    wifiPhy.Set("TxPowerStart", DoubleValue(20.0));
    wifiPhy.Set("TxPowerEnd",   DoubleValue(20.0));

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

    // Standard 500x500 RandomWaypoint
    MobilityHelper mobility;
    ObjectFactory pos;
    pos.SetTypeId("ns3::RandomRectanglePositionAllocator");
    pos.Set("X", StringValue("ns3::UniformRandomVariable[Min=0.0|Max=150.0]"));
    pos.Set("Y", StringValue("ns3::UniformRandomVariable[Min=0.0|Max=150.0]"));
    Ptr<PositionAllocator> taPositionAlloc = pos.Create()->GetObject<PositionAllocator>();

    mobility.SetPositionAllocator(taPositionAlloc);
    mobility.SetMobilityModel("ns3::RandomWaypointMobilityModel",
                              "Speed",             StringValue("ns3::UniformRandomVariable[Min=1.0|Max=20.0]"),
                              "Pause",             StringValue("ns3::ConstantRandomVariable[Constant=2.0]"),
                              "PositionAllocator", PointerValue(taPositionAlloc));
    mobility.Install(nodes);

    AodvHelper aodv;
    InternetStackHelper internet;
    internet.SetRoutingHelper(aodv);
    internet.Install(nodes);

    if (maliciousNode < nNodes) {
        SetNodeMalicious(nodes.Get(maliciousNode), maliciousNode);
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
    ApplicationContainer serverApps = server.Install(nodes.Get(nNodes - 1));
    serverApps.Start(Seconds(1.0));
    serverApps.Stop(Seconds(simulationTime - 1.0));

    UdpEchoClientHelper client(interfaces.GetAddress(nNodes - 1), port);
    client.SetAttribute("MaxPackets", UintegerValue(100));
    client.SetAttribute("Interval",   TimeValue(Seconds(0.5)));
    client.SetAttribute("PacketSize", UintegerValue(1024));

    ApplicationContainer clientApps = client.Install(nodes.Get(0));
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
                std::string timeStr, nodeStr;
                if (std::getline(ss, timeStr, ',') && std::getline(ss, nodeStr, ',')) {
                    double t = std::stod(timeStr);
                    uint32_t nid = std::stoul(nodeStr);
                    Simulator::Schedule(Seconds(t), &ScheduleBlacklist, nodes, nid, t);
                }
            }
        }
    }

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
