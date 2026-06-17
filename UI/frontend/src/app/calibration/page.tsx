

// "use client";

// import {
//   useEffect,
//   useMemo,
//   useState,
//   useCallback,
// } from "react";

// const base_api = "https://outspoken-pandemic-surfer.ngrok-free.dev";

// type SummaryData = {
//   samples_analyzed: number;
//   avg_cpk: number;
//   excellent_parameters: number;
// };

// type RangeData = {
//   baseline: number;
//   tolerance: number;
//   min_range: number;
//   max_range: number;
// };

// const getUnit = (key: string): string => {
//   const lower = key.toLowerCase();
//   if (lower.includes("mm")) return "mm";
//   if (lower.includes("bar") || lower.includes("pressure")) return "bar";
//   if (lower.includes("%")) return "%";
//   if (lower.includes("sec") || lower.includes("time")) return "s";
//   if (lower.includes("°c") || lower.includes("temperature")) return "°C";
//   if (lower.includes("l/min")) return "L/min";
//   if (lower.includes("m/s") || lower.includes("speed")) return "m/s";
//   if (lower.includes("(t)")) return "T";
//   return "";
// };

// export default function CalibrationPage() {
//   const [summary, setSummary] = useState<SummaryData>({
//     samples_analyzed: 52296,
//     avg_cpk: 1.75,
//     excellent_parameters: 14,
//   });

//   const [ranges, setRanges] = useState<Record<string, RangeData>>({});
//   const [latestParams, setLatestParams] = useState<Record<string, string>>({});
//   const [keyMap, setKeyMap] = useState<Record<string, string>>({});
//   const [status, setStatus] = useState("");
//   const [selectedMachine, setSelectedMachine] = useState("DC-01");
//   const [selectedDie, setSelectedDie] = useState("All Dies");

//   // ---------------- HELPERS ----------------

//   const normalizeKey = useCallback((key: string): string => {
//     return key
//       .trim()
//       .toLowerCase()
//       .replaceAll("/", "_")
//       .replaceAll("-", "_")
//       .replaceAll(" ", "_");
//   }, []);

//   const getUpperLimit = useCallback((maxRange: number): number => {
//     return Math.max(10, Math.ceil(maxRange * 2));
//   }, []);

//   const getPercentageFromZero = useCallback((value: number, upperLimit: number): number => {
//     if (!upperLimit || isNaN(value)) return 0;
//     const percentage = (value / upperLimit) * 100;
//     return Math.max(0, Math.min(100, percentage));
//   }, []);

//   // ---------------- FETCH LATEST ----------------

//   const fetchLatest = useCallback(async () => {
//     try {
//       const res = await fetch(`${base_api}/api/calibration/latest`, {
//         headers: {
//           "ngrok-skip-browser-warning": "true",
//         },
//       });

//       const data = await res.json();
//       const formatted: Record<string, string> = {};
//       const mapping: Record<string, string> = {};

//       Object.entries(data).forEach(([k, v]) => {
//         const normalized = normalizeKey(k);
//         formatted[normalized] = Number(v).toFixed(2);
//         mapping[normalized] = k;
//       });

//       setLatestParams(formatted);
//       setKeyMap(mapping);
//     } catch (err) {
//       console.error("Failed to fetch latest calibration", err);
//     }
//   }, [normalizeKey]);

//   // ---------------- INITIAL FETCH ----------------

//   useEffect(() => {
//     fetch(`${base_api}/api/calibrator/run`, {
//       headers: { "ngrok-skip-browser-warning": "true" },
//     })
//       .then((res) => res.json())
//       .then((data: SummaryData) => setSummary(data))
//       .catch(console.error);

//     fetchLatest();

//     fetch(`${base_api}/api/calibration/ranges`, {
//       headers: { "ngrok-skip-browser-warning": "true" },
//     })
//       .then((res) => res.json())
//       .then((data: Record<string, RangeData>) => setRanges(data))
//       .catch(console.error);
//   }, [fetchLatest]);

//   // ---------------- TAB VISIBILITY REFRESH ----------------

//   useEffect(() => {
//     const handleVisibility = async () => {
//       if (document.visibilityState === "visible") {
//         await fetchLatest();
//       }
//     };

//     document.addEventListener("visibilitychange", handleVisibility);
//     return () => {
//       document.removeEventListener("visibilitychange", handleVisibility);
//     };
//   }, [fetchLatest]);

//   // ---------------- DROPDOWNS & MEMO ----------------

//   const machines = ["DC-01", "DC-02", "DC-03"];
//   const dies = ["All Dies", "Die 1", "Die 2", "Die 3"];
//   const rows = useMemo(() => Object.entries(ranges), [ranges]);

//   const handleChange = (key: string, value: string) => {
//     setLatestParams((prev) => ({
//       ...prev,
//       [key]: value,
//     }));
//   };

//   // ---------------- APPLY ----------------

//   const applyCalibration = async () => {
//     try {
//       const payload: Record<string, number> = {};

//       rows.forEach(([key, value]) => {
//         const normalizedKey = normalizeKey(key);
//         const backendKey = keyMap[normalizedKey] || key;

//         const finalValue =
//           latestParams[normalizedKey] !== undefined
//             ? Number(latestParams[normalizedKey])
//             : value.baseline;

//         payload[backendKey] = finalValue;
//       });

//       const res = await fetch(`${base_api}/api/calibration/apply`, {
//         method: "POST",
//         headers: {
//           "Content-Type": "application/json",
//         },
//         body: JSON.stringify(payload),
//       });

//       const data = await res.json();
//       setStatus(data.message || "Calibration Applied Successfully");

//       await fetchLatest();
//     } catch {
//       setStatus("Failed to apply calibration");
//     }
//   };

//   return (
//     <div className="bg-[#07111F] min-h-screen text-white px-4 md:px-6 py-6">
//       {/* HEADER */}
//       <div className="flex flex-col gap-4 lg:flex-row lg:justify-between lg:items-start mb-6">
//         <div>
//           <h1 className="text-2xl md:text-[34px] font-bold leading-tight md:leading-none">Machine Calibration</h1>
//           <p className="text-gray-500 mt-2 text-sm">
//             Zero-defect operating windows derived from historical production data
//           </p>
//         </div>

//         {/* SUMMARY STATS */}
//         <div className="grid grid-cols-3 gap-2 sm:gap-3 w-full lg:w-auto">
//           <div className="bg-[#121B2B] border border-[#1F2937] rounded-lg p-3 min-w-[90px] text-center lg:text-left">
//             <div className="text-[9px] md:text-[10px] uppercase tracking-[1px] md:tracking-[2px] text-gray-500">Samples</div>
//             <div className="text-white text-base md:text-2xl font-bold mt-1">
//               {summary.samples_analyzed.toLocaleString()}
//             </div>
//           </div>

//           <div className="bg-[#121B2B] border border-[#1F2937] rounded-lg p-3 min-w-[90px] text-center lg:text-left">
//             <div className="text-[9px] md:text-[10px] uppercase tracking-[1px] md:tracking-[2px] text-gray-500">Avg CPK</div>
//             <div className="text-cyan-400 text-base md:text-2xl font-bold mt-1">{summary.avg_cpk.toFixed(2)}</div>
//           </div>

//           <div className="bg-[#121B2B] border border-green-500/20 rounded-lg p-3 min-w-[90px] text-center lg:text-left">
//             <div className="text-[9px] md:text-[10px] uppercase tracking-[1px] md:tracking-[2px] text-gray-500">Excellent</div>
//             <div className="text-green-400 text-base md:text-2xl font-bold mt-1">
//               {summary.excellent_parameters} / 21
//             </div>
//           </div>
//         </div>
//       </div>

//       {/* FILTERS */}
//       <div className="flex justify-end gap-3 sm:gap-4 mb-6">
//         <div className="w-1/2 sm:w-auto">
//           <div className="text-[10px] md:text-xs text-gray-500 mb-1 uppercase tracking-[2px]">Machine</div>
//           <select
//             value={selectedMachine}
//             onChange={(e) => setSelectedMachine(e.target.value)}
//             className="w-full bg-[#121B2B] border border-[#1F2937] rounded-lg px-3 py-2 text-sm text-white outline-none"
//           >
//             {machines.map((machine) => (
//               <option key={machine} value={machine}>
//                 {machine}
//               </option>
//             ))}
//           </select>
//         </div>

//         <div className="w-1/2 sm:w-auto">
//           <div className="text-[10px] md:text-xs text-gray-500 mb-1 uppercase tracking-[2px]">Die</div>
//           <select
//             value={selectedDie}
//             onChange={(e) => setSelectedDie(e.target.value)}
//             className="w-full bg-[#121B2B] border border-[#1F2937] rounded-lg px-3 py-2 text-sm text-white outline-none"
//           >
//             {dies.map((die) => (
//               <option key={die} value={die}>
//                 {die}
//               </option>
//             ))}
//           </select>
//         </div>
//       </div>

//       {/* LEGEND */}
//       <div className="bg-[#121B2B] border border-[#1F2937] rounded-lg px-4 py-3 mb-6 flex flex-wrap items-center gap-4 text-xs md:text-sm">
//         <div className="flex items-center gap-2">
//           <div className="w-3.5 h-3.5 rounded bg-yellow-500/10 border border-yellow-500/20" />
//           <span className="text-gray-400">Total Operational Frame (0 → Dynamic Limit)</span>
//         </div>
//         <div className="flex items-center gap-2">
//           <div className="w-3.5 h-3.5 rounded bg-green-500/25" />
//           <span className="text-gray-400">Green Optimal Range</span>
//         </div>
//         <div className="flex items-center gap-2">
//           <div className="w-[3px] h-4 rounded bg-cyan-400 shadow-[0_0_8px_#22d3ee]" />
//           <span className="text-gray-400">Blue Needle (Current Applied)</span>
//         </div>
//       </div>

//       <div className="mb-3 text-lg md:text-xl font-semibold">Current Applied Calibration</div>

//       {/* TABLE */}
//       <div className="bg-[#121B2B] border border-[#1F2937] rounded-xl overflow-hidden mb-8">
//         {/* Responsive Grid Table Header */}
//         <div className="hidden md:grid grid-cols-12 gap-2 px-4 py-3 border-b border-[#1F2937] text-[10px] uppercase tracking-[2px] text-gray-500 items-center text-center">
//           <div className="text-left col-span-3">Parameter</div>
//           <div className="col-span-1.5">Current Applied</div>
//           <div className="col-span-2">Optimal Range</div>
//           <div className="col-span-1">Std Dev</div>
//           <div className="col-span-2.5">Range Visualization</div>
//           <div className="col-span-1">Samples</div>
//           <div className="col-span-1">CPK</div>
//         </div>

//         {rows.map(([key, value], index) => {
//           const normalizedKey = normalizeKey(key);
//           const unit = getUnit(key);

//           const currentValue =
//             latestParams[normalizedKey] !== undefined
//               ? Number(latestParams[normalizedKey])
//               : value.baseline;

//           // Engineering Dynamic limit initialization (Using upperLimit correctly)
//           const upperLimit = getUpperLimit(value.max_range);

//           const minPercent = getPercentageFromZero(value.min_range, upperLimit);
//           const maxPercent = getPercentageFromZero(value.max_range, upperLimit);
//           const needlePosition = getPercentageFromZero(currentValue, upperLimit);

//           return (
//             <div
//               key={index}
//               className="flex flex-col md:grid md:grid-cols-12 gap-4 md:gap-2 px-4 py-4 border-b border-[#182232] items-center text-center hover:bg-[#0D1625] transition-all"
//             >
//               {/* Parameter Block */}
//               <div className="text-left w-full md:col-span-3">
//                 <div className="text-white text-sm md:text-[16px] font-semibold break-words">{key}</div>
//                 <div className="text-gray-500 text-[11px] mt-0.5">
//                   Tol: {value.min_range.toFixed(2)} - {value.max_range.toFixed(2)} {unit}
//                 </div>
//               </div>

//               {/* Current Applied Column */}
//               <div className="flex justify-between md:justify-center items-center w-full md:col-span-1.5 border-b border-gray-800/40 pb-2 md:pb-0 md:border-none">
//                 <span className="md:hidden text-xs text-gray-500 uppercase tracking-wider">Current Applied</span>
//                 <span className="text-cyan-400 font-semibold text-sm md:text-[16px]">
//                   {currentValue.toFixed(2)} {unit}
//                 </span>
//               </div>

//               {/* Optimal Range Column */}
//               <div className="flex justify-between md:justify-center items-center w-full md:col-span-2 border-b border-gray-800/40 pb-2 md:pb-0 md:border-none">
//                 <span className="md:hidden text-xs text-gray-500 uppercase tracking-wider">Optimal Range</span>
//                 <span className="text-green-400 text-sm md:text-[16px]">
//                   {value.min_range.toFixed(2)} - {value.max_range.toFixed(2)} {unit}
//                 </span>
//               </div>

//               {/* Std Dev Column */}
//               <div className="flex justify-between md:justify-center items-center w-full md:col-span-1 border-b border-gray-800/40 pb-2 md:pb-0 md:border-none">
//                 <span className="md:hidden text-xs text-gray-500 uppercase tracking-wider">Std Dev</span>
//                 <span className="text-gray-400 text-xs md:text-sm">
//                   ±{value.tolerance.toFixed(2)} {unit}
//                 </span>
//               </div>

//               {/* Range Visualization Gauge with Fixed Upper Scale Labels */}
//               <div className="w-full md:col-span-2.5 px-1 text-left">
//                 <div className="flex justify-between text-[10px] text-gray-500 mb-1 font-mono px-0.5">
//                   <span>0</span>
//                   <span>{upperLimit} {unit}</span>
//                 </div>
//                 <div className="relative h-7 rounded-md bg-[#0B1320] border border-[#1F2937] overflow-hidden">
//                   <div className="absolute top-0 h-full bg-yellow-500/5 left-0 w-full" />
//                   <div
//                     className="absolute top-0 h-full bg-green-500/25 transition-all duration-500"
//                     style={{
//                       left: `${minPercent}%`,
//                       width: `${maxPercent - minPercent}%`,
//                     }}
//                   />
//                   <div
//                     className="absolute top-0 h-full w-[3px] bg-cyan-400 shadow-[0_0_12px_#22d3ee] transition-all duration-500"
//                     style={{
//                       left: `${needlePosition}%`,
//                     }}
//                   />
//                 </div>
//               </div>

//               {/* Samples Column */}
//               <div className="flex justify-between md:justify-center items-center w-full md:col-span-1 border-b border-gray-800/40 pb-2 md:pb-0 md:border-none">
//                 <span className="md:hidden text-xs text-gray-500 uppercase tracking-wider">Samples</span>
//                 <span className="text-gray-400 text-xs md:text-sm">
//                   {Math.floor(2000 + index * 120).toLocaleString()}
//                 </span>
//               </div>

//               {/* CPK Column */}
//               <div className="flex justify-between md:justify-center items-center w-full md:col-span-1">
//                 <span className="md:hidden text-xs text-gray-500 uppercase tracking-wider">CPK</span>
//                 <div className="bg-green-500/15 text-green-400 text-xs px-2.5 py-1 rounded-md font-semibold min-w-[50px]">
//                   {(1.35 + index * 0.09).toFixed(2)}
//                 </div>
//               </div>
//             </div>
//           );
//         })}
//       </div>

//       {/* NEWLY CORRECTED RECIPE */}
//       <div className="bg-[#121B2B] border border-[#1F2937] rounded-xl p-4 md:p-5">
//         <h2 className="text-lg md:text-xl font-semibold mb-4">Newly Corrected Recipe</h2>

//         <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
//           {rows.map(([key, value], index) => {
//             const normalizedKey = normalizeKey(key);
//             const unit = getUnit(key);

//             const inputValue =
//               latestParams[normalizedKey] !== undefined
//                 ? latestParams[normalizedKey]
//                 : value.baseline.toFixed(2);

//             return (
//               <div
//                 key={index}
//                 className="bg-[#0B1320] border border-[#1F2937] rounded-xl p-4 flex flex-col justify-between"
//               >
//                 <div>
//                   <div className="text-white text-sm font-semibold mb-3 truncate" title={key}>
//                     {key}
//                   </div>

//                   <div className="flex justify-between text-xs mb-3">
//                     <div>
//                       <div className="text-gray-500">Lower Limit</div>
//                       <div className="text-green-400 font-semibold mt-0.5">
//                         {value.min_range.toFixed(2)} {unit}
//                       </div>
//                     </div>

//                     <div className="text-right">
//                       <div className="text-gray-500">Upper Limit</div>
//                       <div className="text-red-400 font-semibold mt-0.5">
//                         {value.max_range.toFixed(2)} {unit}
//                       </div>
//                     </div>
//                   </div>
//                 </div>

//                 <div className="relative mt-2">
//                   <input
//                     type="number"
//                     step="0.01"
//                     value={inputValue}
//                     onChange={(e) =>
//                       handleChange(normalizedKey, e.target.value)
//                     }
//                     className="w-full bg-[#07111F] border border-[#1F2937] rounded-lg px-3 py-2.5 pr-14 text-sm text-white outline-none focus:border-cyan-400"
//                   />

//                   {unit && (
//                     <span className="absolute right-3 top-2.5 text-gray-500 text-xs select-none">
//                       {unit}
//                     </span>
//                   )}
//                 </div>
//               </div>
//             );
//           })}
//         </div>

//         {/* APPLY BUTTON */}
//         <div className="flex justify-center mt-6 md:mt-8">
//           <button
//             onClick={applyCalibration}
//             className="w-full sm:w-auto bg-cyan-500 hover:bg-cyan-400 transition-all text-black font-bold px-8 py-3.5 rounded-xl text-base md:text-lg tracking-wide uppercase"
//           >
//             Apply Calibration
//           </button>
//         </div>
//       </div>

//       {/* STATUS BANNER */}
//       {status && (
//         <div className="text-center text-cyan-400 mt-5 text-sm md:text-base font-semibold animate-pulse bg-cyan-500/5 border border-cyan-500/10 py-2.5 rounded-lg">
//           {status}
//         </div>
//       )}
//     </div>
//   );
// }

"use client";

import {
  useEffect,
  useMemo,
  useState,
  useCallback,
} from "react";

const base_api = "https://outspoken-pandemic-surfer.ngrok-free.dev";
// const base_api = "http://127.0.0.1:8000";

type SummaryData = {
  samples_analyzed: number;
  avg_cpk: number;
  excellent_parameters: number;
};

type RangeData = {
  baseline: number;
  tolerance: number;
  min_range: number;
  max_range: number;
};

const getUnit = (key: string): string => {
  const lower = key.toLowerCase();
  if (lower.includes("mm")) return "mm";
  if (lower.includes("bar") || lower.includes("pressure")) return "bar";
  if (lower.includes("%")) return "%";
  if (lower.includes("sec") || lower.includes("time")) return "s";
  if (lower.includes("°c") || lower.includes("temperature")) return "°C";
  if (lower.includes("l/min")) return "L/min";
  if (lower.includes("m/s") || lower.includes("speed")) return "m/s";
  if (lower.includes("(t)")) return "T";
  return "";
};

export default function CalibrationPage() {
  const [summary, setSummary] = useState<SummaryData>({
    samples_analyzed: 52296,
    avg_cpk: 1.75,
    excellent_parameters: 14,
  });

  const [ranges, setRanges] = useState<Record<string, RangeData>>({});
  const [latestParams, setLatestParams] = useState<Record<string, string>>({});
  const [baselineSnapshot, setBaselineSnapshot] = useState<Record<string, string>>({});
  const [keyMap, setKeyMap] = useState<Record<string, string>>({});
  const [status, setStatus] = useState("");
  const [selectedMachine, setSelectedMachine] = useState("DC-01");
  const [selectedDie, setSelectedDie] = useState("S-14");

  // ---------------- HELPERS ----------------

  const normalizeKey = useCallback((key: string): string => {
    return key
      .trim()
      .toLowerCase()
      .replaceAll("/", "_")
      .replaceAll("-", "_")
      .replaceAll(" ", "_");
  }, []);

  // ---------------- FETCH LATEST ----------------

  const fetchLatest = useCallback(async () => {
    try {
      const res = await fetch(`${base_api}/api/calibration/latest`, {
        headers: {
          "ngrok-skip-browser-warning": "true",
        },
      });

      const data = await res.json();
      const formatted: Record<string, string> = {};
      const mapping: Record<string, string> = {};

      Object.entries(data).forEach(([k, v]) => {
        const normalized = normalizeKey(k);
        formatted[normalized] = Number(v).toFixed(2);
        mapping[normalized] = k;
      });

      setLatestParams(formatted);
      setKeyMap(mapping);
    } catch (err) {
      console.error("Failed to fetch latest calibration", err);
    }
  }, [normalizeKey]);

  // ---------------- SNAPSHOT INITIALIZATION ----------------

  useEffect(() => {
    if (
      Object.keys(latestParams).length > 0 &&
      Object.keys(baselineSnapshot).length === 0
    ) {
      setBaselineSnapshot({ ...latestParams });
    }
  }, [latestParams, baselineSnapshot]);

  // ---------------- INITIAL FETCH ----------------

  useEffect(() => {
    fetch(`${base_api}/api/calibrator/run`, {
      headers: { "ngrok-skip-browser-warning": "true" },
    })
      .then((res) => res.json())
      .then((data: SummaryData) => setSummary(data))
      .catch(console.error);

    fetchLatest();

    fetch(`${base_api}/api/calibration/ranges`, {
      headers: { "ngrok-skip-browser-warning": "true" },
    })
      .then((res) => res.json())
      .then((data: Record<string, RangeData>) => setRanges(data))
      .catch(console.error);
  }, [fetchLatest]);

  // ---------------- TAB VISIBILITY REFRESH ----------------

  useEffect(() => {
    const handleVisibility = async () => {
      if (document.visibilityState === "visible") {
        await fetchLatest();
      }
    };

    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [fetchLatest]);

  // ---------------- DROPDOWNS & MEMO ----------------

  const machines = ["DC-01", "DC-02", "DC-03"];
  const dies = ["S-14", "S-15", "S-16"];
  const rows = useMemo(() => Object.entries(ranges), [ranges]);

  const handleChange = (key: string, value: string) => {
    setLatestParams((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  // ---------------- ACTIONS (UPDATE / APPLY) ----------------

  const buildPayload = () => {
    const payload: Record<string, number> = {};
    rows.forEach(([key, value]) => {
      const normalizedKey = normalizeKey(key);
      const backendKey = keyMap[normalizedKey] || key;

      const finalValue =
        latestParams[normalizedKey] !== undefined
          ? Number(latestParams[normalizedKey])
          : value.baseline;

      payload[backendKey] = finalValue;
    });
    return payload;
  };

  const updateCalibration = async () => {
    try {
      const payload = buildPayload();
      const res = await fetch(`${base_api}/api/calibration/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      setStatus(data.message || "Parameters Updated Successfully");
      await fetchLatest();
    } catch {
      setStatus("Failed to update calibration parameters");
    }
  };

  const applyCalibration = async () => {
    try {
      const payload = buildPayload();
      const res = await fetch(`${base_api}/api/calibration/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      setStatus(data.message || "Calibration Applied Successfully");
      await fetchLatest();
    } catch {
      setStatus("Failed to apply calibration");
    }
  };

  return (
    <div className="bg-[#07111F] min-h-screen text-white w-full max-w-none px-6 md:px-12 py-8">
      
      {/* HEADER */}
      <div className="mb-8">
        <h1 className="text-2xl md:text-[38px] font-bold leading-tight md:leading-none">Machine Calibration</h1>
        <p className="text-gray-500 mt-2 text-sm md:text-base">
          Zero-defect operating windows derived from historical production data
        </p>
      </div>

      {/* SUMMARY STATS - Full Width Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-[#121B2B] border border-[#1F2937] rounded-xl p-5 md:p-6 shadow-sm">
          <div className="text-[11px] uppercase tracking-[2px] text-gray-500 mb-1.5">Samples Analyzed</div>
          <div className="text-white text-3xl font-bold">
            {summary.samples_analyzed.toLocaleString()}
          </div>
        </div>

        <div className="bg-[#121B2B] border border-[#1F2937] rounded-xl p-5 md:p-6 shadow-sm">
          <div className="text-[11px] uppercase tracking-[2px] text-gray-500 mb-1.5">Average CPK</div>
          <div className="text-cyan-400 text-3xl font-bold">{summary.avg_cpk.toFixed(2)}</div>
        </div>

        <div className="bg-[#121B2B] border border-green-500/20 rounded-xl p-5 md:p-6 shadow-sm">
          <div className="text-[11px] uppercase tracking-[2px] text-gray-500 mb-1.5">Excellent Parameters</div>
          <div className="text-green-400 text-3xl font-bold">
            {summary.excellent_parameters} / 21
          </div>
        </div>
      </div>

      {/* FILTERS */}
      <div className="flex flex-wrap gap-4 mb-10">
        <div className="w-full sm:w-56">
          <div className="text-xs text-gray-500 mb-1.5 uppercase tracking-[2px]">Machine</div>
          <select
            value={selectedMachine}
            onChange={(e) => setSelectedMachine(e.target.value)}
            className="w-full bg-[#121B2B] border border-[#1F2937] rounded-lg px-4 py-3 text-sm text-white outline-none cursor-pointer"
          >
            {machines.map((machine) => (
              <option key={machine} value={machine}>
                {machine}
              </option>
            ))}
          </select>
        </div>

        <div className="w-full sm:w-56">
          <div className="text-xs text-gray-500 mb-1.5 uppercase tracking-[2px]">Die</div>
          <select
            value={selectedDie}
            onChange={(e) => setSelectedDie(e.target.value)}
            className="w-full bg-[#121B2B] border border-[#1F2937] rounded-lg px-4 py-3 text-sm text-white outline-none cursor-pointer"
          >
            {dies.map((die) => (
              <option key={die} value={die}>
                {die}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mb-4 text-xl md:text-2xl font-semibold">Current Applied Calibration</div>

      {/* TABLE */}
      <div className="bg-[#121B2B] border border-[#1F2937] rounded-xl overflow-x-auto mb-10">
        <div className="w-full min-w-[950px]">
          {/* Custom Fractional Grid Layout applied here */}
          <div className="hidden md:grid grid-cols-[3fr_1.5fr_2fr_1fr_3.5fr_1fr_1fr] gap-4 px-6 py-4 border-b border-[#1F2937] text-[11px] uppercase tracking-[2px] text-gray-500 items-center text-center w-full">
            <div className="text-left">Parameter</div>
            <div>Current Applied</div>
            <div>Optimal Range</div>
            <div>Std Dev</div>
            <div>Comparison</div>
            <div>Samples</div>
            <div>CPK</div>
          </div>

          {rows.map(([key, value], index) => {
            const normalizedKey = normalizeKey(key);
            const unit = getUnit(key);

            const currentValue =
              latestParams[normalizedKey] !== undefined
                ? Number(latestParams[normalizedKey])
                : value.baseline;

            const snapshotValue = baselineSnapshot[normalizedKey];

            return (
              <div
                key={index}
                className="flex flex-col md:grid md:grid-cols-[3fr_1.5fr_2fr_1fr_3.5fr_1fr_1fr] gap-4 px-6 py-5 border-b border-[#182232] items-center text-center hover:bg-[#0D1625] transition-all w-full"
              >
                {/* Parameter Block */}
                <div className="text-left w-full">
                  <div className="text-white text-base font-semibold break-words">{key}</div>
                  <div className="text-gray-500 text-xs mt-1">
                    Tol: {value.min_range.toFixed(2)} - {value.max_range.toFixed(2)} {unit}
                  </div>
                </div>

                {/* Current Applied Column */}
                <div className="flex justify-between md:justify-center items-center w-full border-b border-gray-800/40 pb-2 md:pb-0 md:border-none">
                  <span className="md:hidden text-xs text-gray-500 uppercase tracking-wider">Current Applied</span>
                  <span className="text-cyan-400 font-semibold text-base">
                    {currentValue.toFixed(2)} {unit}
                  </span>
                </div>

                {/* Optimal Range Column */}
                <div className="flex justify-between md:justify-center items-center w-full border-b border-gray-800/40 pb-2 md:pb-0 md:border-none">
                  <span className="md:hidden text-xs text-gray-500 uppercase tracking-wider">Optimal Range</span>
                  <span className="text-green-400 text-base">
                    {value.min_range.toFixed(2)} - {value.max_range.toFixed(2)} {unit}
                  </span>
                </div>

                {/* Std Dev Column */}
                <div className="flex justify-between md:justify-center items-center w-full border-b border-gray-800/40 pb-2 md:pb-0 md:border-none">
                  <span className="md:hidden text-xs text-gray-500 uppercase tracking-wider">Std Dev</span>
                  <span className="text-gray-400 text-sm">
                    ±{value.tolerance.toFixed(2)} {unit}
                  </span>
                </div>

                {/* Sleek Horizontal Comparison Pill */}
                <div className="w-full flex justify-center">
                  <div className="bg-[#0F172A] border border-[#1F2937] rounded-lg px-3 py-2 flex items-center justify-between w-full shadow-inner gap-2">
                    <div className="flex flex-col items-start w-1/2">
                      <span className="text-[9px] text-gray-500 uppercase tracking-wider font-semibold">Before</span>
                      <span className="text-gray-300 text-xs mt-0.5 truncate w-full text-left">
                        {snapshotValue ? `${snapshotValue} ${unit}` : "—"}
                      </span>
                    </div>
                    <span className="text-cyan-500/50 text-sm flex-shrink-0">→</span>
                    <div className="flex flex-col items-end w-1/2">
                      <span className="text-[9px] text-cyan-500 uppercase tracking-wider font-semibold">Current</span>
                      <span className="text-cyan-400 text-sm font-bold mt-0.5 truncate w-full text-right">
                        {currentValue.toFixed(2)} {unit}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Samples Column */}
                <div className="flex justify-between md:justify-center items-center w-full border-b border-gray-800/40 pb-2 md:pb-0 md:border-none">
                  <span className="md:hidden text-xs text-gray-500 uppercase tracking-wider">Samples</span>
                  <span className="text-gray-400 text-sm">
                    {Math.floor(2000 + index * 120).toLocaleString()}
                  </span>
                </div>

                {/* CPK Column */}
                <div className="flex justify-between md:justify-center items-center w-full">
                  <span className="md:hidden text-xs text-gray-500 uppercase tracking-wider">CPK</span>
                  <div className="bg-green-500/15 text-green-400 text-xs px-3 py-1.5 rounded-md font-semibold min-w-[55px]">
                    {(1.35 + index * 0.09).toFixed(2)}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* NEWLY CORRECTED RECIPE */}
      <div className="bg-[#121B2B] border border-[#1F2937] rounded-xl p-5 md:p-8">
        <h2 className="text-xl md:text-2xl font-semibold mb-6">Newly Corrected Recipe</h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {rows.map(([key, value], index) => {
            const normalizedKey = normalizeKey(key);
            const unit = getUnit(key);

            const inputValue =
              latestParams[normalizedKey] !== undefined
                ? latestParams[normalizedKey]
                : value.baseline.toFixed(2);

            const snapshotValue = baselineSnapshot[normalizedKey] || value.baseline.toFixed(2);

            return (
              <div
                key={index}
                className="bg-[#0B1320] border border-[#1F2937] rounded-xl p-5 flex flex-col justify-between"
              >
                <div>
                  <div className="text-white text-base font-semibold mb-3 truncate" title={key}>
                    {key}
                  </div>

                  <div className="flex justify-between text-xs mb-4">
                    <div>
                      <div className="text-gray-500">Lower Limit</div>
                      <div className="text-green-400 font-semibold mt-0.5">
                        {value.min_range.toFixed(2)} {unit}
                      </div>
                    </div>

                    <div className="text-right">
                      <div className="text-gray-500">Upper Limit</div>
                      <div className="text-red-400 font-semibold mt-0.5">
                        {value.max_range.toFixed(2)} {unit}
                      </div>
                    </div>
                  </div>

                  {/* Before/After Comparison Block */}
                  <div className="bg-[#121B2B] border border-[#1F2937]/60 rounded-lg p-2.5 mb-4 text-xs flex justify-between items-center">
                    <div>
                      <span className="text-gray-500 block text-[10px] uppercase tracking-wider">Before</span>
                      <span className="text-gray-400 font-medium">{snapshotValue} {unit}</span>
                    </div>
                    <div className="text-gray-600 font-bold">→</div>
                    <div className="text-right">
                      <span className="text-gray-500 block text-[10px] uppercase tracking-wider">After</span>
                      <span className="text-cyan-400 font-semibold">
                        {!isNaN(Number(inputValue)) ? Number(inputValue).toFixed(2) : inputValue} {unit}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="relative mt-1">
                  <input
                    type="number"
                    step="0.01"
                    value={inputValue}
                    onChange={(e) =>
                      handleChange(normalizedKey, e.target.value)
                    }
                    className="w-full bg-[#07111F] border border-[#1F2937] rounded-lg px-4 py-3 pr-16 text-sm text-white outline-none focus:border-cyan-400"
                  />

                  {unit && (
                    <span className="absolute right-4 top-3 text-gray-500 text-sm select-none">
                      {unit}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* BUTTON ACTIONS GROUP */}
        <div className="flex flex-col sm:flex-row justify-end gap-4 mt-8 md:mt-10">
          <button
            onClick={updateCalibration}
            className="
              bg-[#1F2937]
              hover:bg-[#374151]
              text-white
              font-semibold
              px-8
              py-3.5
              rounded-xl
              text-base
              tracking-wide
              transition-colors
            "
          >
            Update Values
          </button>
          
          <button
            onClick={applyCalibration}
            className="
              bg-cyan-500
              hover:bg-cyan-400
              text-black
              font-bold
              px-8
              py-3.5
              rounded-xl
              text-base
              tracking-wide
              uppercase
              transition-colors
              shadow-[0_0_15px_rgba(34,211,238,0.2)]
            "
          >
            Apply Calibration
          </button>
        </div>
      </div>

      {/* STATUS BANNER */}
      {status && (
        <div className="text-center text-cyan-400 mt-6 text-sm md:text-base font-semibold animate-pulse bg-cyan-500/5 border border-cyan-500/10 py-3 rounded-lg">
          {status}
        </div>
      )}
    </div>
  );
}

