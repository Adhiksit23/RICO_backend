// "use client";

// import { useEffect, useState } from "react";
// import GaugeCard from "@/components/GaugeCard";
// import ParameterGauge from "@/components/ParameterGauge";

// // 1 & 2. Accurate mapping dictionary aligned exactly with your teammate's backend response
// const parameterMap = [
//   { label: "Cooling Time", key: "CURING TIME", unit: "s" },
//   { label: "Spray Time", key: "SPRAY TIME", unit: "s" },
//   { label: "Speed 2", key: "V2", unit: "m/s" },
//   { label: "Speed 4", key: "V4", unit: "m/s" },
//   { label: "Acc Position", key: "ACCEL. POINT", unit: "mm" },
//   { label: "Deacc Position", key: "DEACEL. POINT", unit: "mm" },
//   { label: "Intensification Time", key: "INTEN. TIME", unit: "msec" },
//   { label: "Metal Pressure", key: "METAL PRESS.", unit: "MPa" },
//   { label: "Biscuit Thickness", key: "BISCUIT THICKNESS", unit: "mm" },
//   { label: "Clamp Force", key: "CLAMP FORCE", unit: "%" },
//   { label: "Metal Temperature", key: "FURNACE METAL TEMP.", unit: "°C" },
// ];

// export default function MonitorPage() {
//   const [predictionData, setPredictionData] = useState({
//     non_filling: 0,
//     blowhole: 0,
//     porosity: 0,
//     crack: 0,
//     shrinkage: 0,
//     chipoff: 0,
//   });

//   // 5. Clean array-ready initialization to avoid conditional null checking bloat
//   const [monitorData, setMonitorData] = useState<any[]>([]);

//   useEffect(() => {
//     const fetchData = () => {
//       Promise.all([
//         fetch("http://127.0.0.1:8000/api/predictor/predict").then((res) => res.json()),
//         fetch("http://127.0.0.1:8000/api/predictor/monitor").then((res) => res.json()),
//       ])
//         .then(([predictRes, monitorRes]) => {
//           setPredictionData(predictRes);
//           setMonitorData(monitorRes);
//         })
//         .catch((err) => {
//           console.error("Error fetching dashboard data:", err);
//         });
//     };

//     fetchData();

//     // Refresh every 1 minute
//     const interval = setInterval(fetchData, 60000);

//     return () => clearInterval(interval);
//   }, []);

//   const getPredictionStatus = (value: number) => {
//     if (value < 10) return { status: "LOW", color: "#22C55E" };
//     if (value <= 50) return { status: "MED", color: "#F59E0B" };
//     return { status: "HIGH", color: "#EF4444" };
//   };

//   const predictions = [
//     {
//       label: "Non-filling",
//       subtitle: "Incomplete cavity fill",
//       value: predictionData.non_filling,
//       ...getPredictionStatus(predictionData.non_filling),
//     },
//     {
//       label: "Blowhole",
//       subtitle: "Trapped gas cavities",
//       value: predictionData.blowhole,
//       ...getPredictionStatus(predictionData.blowhole),
//     },
//     {
//       label: "Porosity",
//       subtitle: "Micro voids in structure",
//       value: predictionData.porosity,
//       ...getPredictionStatus(predictionData.porosity),
//     },
//     {
//       label: "Shrinkage",
//       subtitle: "Volumetric contraction",
//       value: predictionData.shrinkage,
//       ...getPredictionStatus(predictionData.shrinkage),
//     },
//     {
//       label: "Chip-off",
//       subtitle: "Surface fragment loss",
//       value: predictionData.chipoff,
//       ...getPredictionStatus(predictionData.chipoff),
//     },
//     {
//       label: "Crack",
//       subtitle: "Structural fracture lines",
//       value: predictionData.crack,
//       ...getPredictionStatus(predictionData.crack),
//     },
//   ];

//   // Map backend telemetry payload onto parameters UI cleanly
//   const raw = monitorData[0];
//   const calibration = monitorData[1];
//   const isDataLoaded = !!(raw && calibration);

//   const parameters = isDataLoaded
//     ? parameterMap.map((item) => {
//         const value = raw[item.key] ?? 0;
//         const range = calibration[item.key] || { lower_tolerance: 0, upper_tolerance: 0 };
//         const isOk = value >= range.lower_tolerance && value <= range.upper_tolerance;

//         return {
//           name: item.label,
//           value: `${value} ${item.unit}`,
//           tolerance: `${range.lower_tolerance.toFixed(2)} - ${range.upper_tolerance.toFixed(2)} ${item.unit}`,
//           status: isOk ? "OK" : "FAIL",
//         };
//       })
//     : [];

//   // Dynamic parameters count
//   const totalParamsCount = parameters.length;
//   const okCount = parameters.filter((p) => p.status === "OK").length;

//   return (
//     <div className="bg-[#0B1120] min-h-screen text-white px-6 py-5">
//       {/* Header */}
//       <div className="flex justify-between items-start mb-5">
//         <div>
//           <h1 className="text-[38px] font-bold leading-none">
//             Die Casting Process Monitor
//           </h1>
//           <p className="text-gray-500 mt-2 text-sm">
//             Live IoT parameters • Post-cast defect prediction
//           </p>
//         </div>

//         {/* Right Info */}
//         <div className="flex gap-8 text-right mt-1">
//           <div>
//             <div className="text-gray-500 text-[10px] uppercase tracking-[2px]">
//               Part ID
//             </div>
//             <div className="text-cyan-400 font-semibold text-sm mt-1">
//               DC-2026-47905
//             </div>
//           </div>

//           <div>
//             <div className="text-gray-500 text-[10px] uppercase tracking-[2px]">
//               Timestamp
//             </div>
//             {/* 3. Intentionally hardcoded until teammate provides an endpoint timestamp field */}
//             <div className="text-white text-sm mt-1">
//               4/30/2026 6:51:13 AM
//             </div>
//           </div>

//           <div>
//             <div className="text-gray-500 text-[10px] uppercase tracking-[2px]">
//               Verdict
//             </div>
//             {/* 4. Maintained layout design with explicit REJECT until backend architecture is clear */}
//             <div className="text-red-400 font-semibold text-sm mt-1">
//               REJECT
//             </div>
//           </div>

//           <div>
//             <div className="text-gray-500 text-[10px] uppercase tracking-[2px]">
//               Params
//             </div>
//             {/* Dynamic counter remains operational */}
//             <div className="text-yellow-400 font-semibold text-sm mt-1">
//               {isDataLoaded ? `${okCount}/${totalParamsCount} OK` : "0/0 OK"}
//             </div>
//           </div>

//           <div className="w-3 h-3 bg-green-400 rounded-full mt-6" />
//         </div>
//       </div>

//       {/* Prediction Header */}
//       <div className="mb-3">
//         <h2 className="text-[15px] font-semibold uppercase tracking-[2px]">
//           POST-CAST DEFECT PREDICTION
//         </h2>
//         <p className="text-gray-500 text-xs mt-1">
//           Top 6 defect modes • AI-inferred from upstream parameters
//         </p>
//       </div>

//       {/* Prediction Cards */}
//       <div className="grid grid-cols-6 gap-4 mb-6">
//         {predictions.map((item) => (
//           <GaugeCard
//             key={item.label}
//             label={item.label}
//             subtitle={item.subtitle}
//             value={item.value}
//             status={item.status}
//             color={item.color}
//           />
//         ))}
//       </div>

//       {/* Parameters Header */}
//       <div className="mb-3">
//         <h2 className="text-[15px] font-semibold uppercase tracking-[2px]">
//           LIVE PROCESS PARAMETERS
//         </h2>
//         <p className="text-gray-500 text-xs mt-1">
//           {isDataLoaded ? totalParamsCount : 0} key parameters monitored against tolerance limits
//         </p>
//       </div>

//       {/* Parameters Grid */}
//       <div className="grid grid-cols-4 gap-4">
//         {isDataLoaded ? (
//           parameters.map((item) => (
//             <ParameterGauge
//               key={item.name}
//               name={item.name}
//               value={item.value}
//               tolerance={item.tolerance}
//               status={item.status}
//             />
//           ))
//         ) : (
//           <div className="col-span-4 text-center py-6 text-gray-500 text-sm">
//             Loading real-time parameter data...
//           </div>
//         )}
//       </div>

//       {/* Footer */}
//       <div className="text-center text-gray-500 text-xs mt-5">
//         Data refreshes every 1 minute • Simulated IoT feed
//       </div>
//     </div>
//   );
// }
"use client";

import { useEffect, useState } from "react";
import GaugeCard from "@/components/GaugeCard";
import ParameterGauge from "@/components/ParameterGauge";

const parameterMap = [
  { label: "Cooling Time", key: "CURING TIME", unit: "s" },
  { label: "Spray Time", key: "SPRAY TIME", unit: "s" },
  { label: "Speed 2", key: "V2", unit: "m/s" },
  { label: "Speed 4", key: "V4", unit: "m/s" },
  { label: "Acc Position", key: "ACCEL. POINT", unit: "mm" },
  { label: "Deacc Position", key: "DEACEL. POINT", unit: "mm" },
  { label: "Intensification Time", key: "INTEN. TIME", unit: "msec" },
  { label: "Metal Pressure", key: "METAL PRESS.", unit: "MPa" },
  { label: "Biscuit Thickness", key: "BISCUIT THICKNESS", unit: "mm" },
  { label: "Clamp Force", key: "CLAMP FORCE", unit: "%" },
  { label: "Metal Temperature", key: "FURNACE METAL TEMP.", unit: "°C" },
];


// const parameterMap = [
//   { label: "Cooling Time", key: "CURING TIME", unit: "s" },
//   { label: "Spray Time", key: "SPRAY TIME", unit: "s" },
//   { label: "Speed 2", key: "V2", unit: "m/s" },
//   { label: "Speed 4", key: "V4", unit: "m/s" },
//   { label: "Acc Position", key: "ACCEL. POINT", unit: "mm" },
//   { label: "Deacc Position", key: "DEACEL. POINT", unit: "mm" },
//   { label: "Intensification Time", key: "INTEN. TIME", unit: "msec" },
//   { label: "Metal Pressure", key: "METAL PRESS.", unit: "MPa" },
//   { label: "Biscuit Thickness", key: "BISCUIT THICKNESS", unit: "mm" },
//   { label: "Clamp Force", key: "CLAMP FORCE", unit: "%" },
//   { label: "Metal Temperature", key: "FURNACE METAL TEMP.", unit: "°C" },
// ];

export default function MonitorPage() {
  const [predictionData, setPredictionData] = useState({
    non_filling: 0,
    blowhole: 0,
    porosity: 0,
    crack: 0,
    shrinkage: 0,
    chipoff: 0,
  });

  const [monitorData, setMonitorData] = useState<any[]>([]);
  const [isUpdating, setIsUpdating] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      setIsUpdating(true);

      // 1. Await update and verify HTTP response success before pulling down current state
      try {
        const response = await fetch("http://127.0.0.1:8000/api/predictor/update");
        
        if (!response.ok) {
          throw new Error(`Update endpoint returned status: ${response.status}`);
        }
      } catch (err) {
        console.warn("IoT update failed:", err);
      }

      // 2. Query UI dashboard telemetry payloads sequentially from backend database
      try {
        const [predictRes, monitorRes] = await Promise.all([
          fetch("http://127.0.0.1:8000/api/predictor/predict").then((res) => res.json()),
          fetch("http://127.0.0.1:8000/api/predictor/monitor").then((res) => res.json()),
        ]);

        setPredictionData(predictRes);
        setMonitorData(monitorRes);
      } catch (err) {
        console.error("Error fetching dashboard data:", err);
      } finally {
        setIsUpdating(false);
      }
    };

    fetchData();

    // Set interval loop to trigger cycle every 1 minute
    const interval = setInterval(fetchData, 60000);

    return () => clearInterval(interval);
  }, []);

  const getPredictionStatus = (value: number) => {
    if (value < 10) return { status: "LOW", color: "#22C55E" };
    if (value <= 50) return { status: "MED", color: "#F59E0B" };
    return { status: "HIGH", color: "#EF4444" };
  };

  const predictions = [
    {
      label: "Non-filling",
      subtitle: "Incomplete cavity fill",
      value: predictionData.non_filling,
      ...getPredictionStatus(predictionData.non_filling),
    },
    {
      label: "Blowhole",
      subtitle: "Trapped gas cavities",
      value: predictionData.blowhole,
      ...getPredictionStatus(predictionData.blowhole),
    },
    {
      label: "Porosity",
      subtitle: "Micro voids in structure",
      value: predictionData.porosity,
      ...getPredictionStatus(predictionData.porosity),
    },
    {
      label: "Shrinkage",
      subtitle: "Volumetric contraction",
      value: predictionData.shrinkage,
      ...getPredictionStatus(predictionData.shrinkage),
    },
    {
      label: "Chip-off",
      subtitle: "Surface fragment loss",
      value: predictionData.chipoff,
      ...getPredictionStatus(predictionData.chipoff),
    },
    {
      label: "Crack",
      subtitle: "Structural fracture lines",
      value: predictionData.crack,
      ...getPredictionStatus(predictionData.crack),
    },
  ];

  const raw = monitorData[0];
  const calibration = monitorData[1];
  const isDataLoaded = !!(raw && calibration);

  const parameters = isDataLoaded
    ? parameterMap.map((item) => {
        const value = raw[item.key] ?? 0;
        const range = calibration[item.key] || { lower_tolerance: 0, upper_tolerance: 0 };
        const isOk = value >= range.lower_tolerance && value <= range.upper_tolerance;

        return {
          name: item.label,
          value: `${value} ${item.unit}`,
          tolerance: `${range.lower_tolerance.toFixed(2)} - ${range.upper_tolerance.toFixed(2)} ${item.unit}`,
          status: isOk ? "OK" : "FAIL",
        };
      })
    : [];

  const totalParamsCount = parameters.length;
  const okCount = parameters.filter((p) => p.status === "OK").length;

  return (
    <div className="bg-[#0B1120] min-h-screen text-white px-6 py-5">
      {/* Header */}
      <div className="flex justify-between items-start mb-5">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-[38px] font-bold leading-none">
              Die Casting Process Monitor
            </h1>
            {isUpdating && (
              <span className="text-xs bg-cyan-950 text-cyan-400 border border-cyan-800 px-2 py-0.5 rounded animate-pulse mt-1">
                Updating IoT Data...
              </span>
            )}
          </div>
          <p className="text-gray-500 mt-2 text-sm">
            Live IoT parameters • Post-cast defect prediction
          </p>
        </div>

        {/* Right Info */}
        <div className="flex gap-8 text-right mt-1">
          <div>
            <div className="text-gray-500 text-[10px] uppercase tracking-[2px]">
              Part ID
            </div>
            <div className="text-cyan-400 font-semibold text-sm mt-1">
              DC-2026-47905
            </div>
          </div>

          <div>
            <div className="text-gray-500 text-[10px] uppercase tracking-[2px]">
              Timestamp
            </div>
            <div className="text-white text-sm mt-1">
              4/30/2026 6:51:13 AM
            </div>
          </div>

          <div>
            <div className="text-gray-500 text-[10px] uppercase tracking-[2px]">
              Verdict
            </div>
            <div className="text-red-400 font-semibold text-sm mt-1">
              REJECT
            </div>
          </div>

          <div>
            <div className="text-gray-500 text-[10px] uppercase tracking-[2px]">
              Params
            </div>
            <div className="text-yellow-400 font-semibold text-sm mt-1">
              {isDataLoaded ? `${okCount}/${totalParamsCount} OK` : "0/0 OK"}
            </div>
          </div>

          <div className="w-3 h-3 bg-green-400 rounded-full mt-6" />
        </div>
      </div>

      {/* Prediction Header */}
      <div className="mb-3">
        <h2 className="text-[15px] font-semibold uppercase tracking-[2px]">
          POST-CAST DEFECT PREDICTION
        </h2>
        <p className="text-gray-500 text-xs mt-1">
          Top 6 defect modes • AI-inferred from upstream parameters
        </p>
      </div>

      {/* Prediction Cards */}
      <div className="grid grid-cols-6 gap-4 mb-6">
        {predictions.map((item) => (
          <GaugeCard
            key={item.label}
            label={item.label}
            subtitle={item.subtitle}
            value={item.value}
            status={item.status}
            color={item.color}
          />
        ))}
      </div>

      {/* Parameters Header */}
      <div className="mb-3">
        <h2 className="text-[15px] font-semibold uppercase tracking-[2px]">
          LIVE PROCESS PARAMETERS
        </h2>
        <p className="text-gray-500 text-xs mt-1">
          {isDataLoaded ? totalParamsCount : 0} key parameters monitored against tolerance limits
        </p>
      </div>

      {/* Parameters Grid */}
      <div className="grid grid-cols-4 gap-4">
        {isDataLoaded ? (
          parameters.map((item) => (
            <ParameterGauge
              key={item.name}
              name={item.name}
              value={item.value}
              tolerance={item.tolerance}
              status={item.status}
            />
          ))
        ) : (
          <div className="col-span-4 text-center py-6 text-gray-500 text-sm">
            Performing primary telemetry fetch sequence...
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="text-center text-gray-500 text-xs mt-5">
        Data refreshes every 1 minute • Simulated IoT feed
      </div>
    </div>
  );
}