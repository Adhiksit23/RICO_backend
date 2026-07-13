// "use client";

// import {
//   useEffect,
//   useMemo,
//   useState,
//   useCallback,
// } from "react";

// // const base_api = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

// const base_api = "https://outspoken-pandemic-surfer.ngrok-free.dev"

// type RangeData = {
//   baseline: number;
//   tolerance: number;
//   min_range: number;
//   max_range: number;
//   unit?: string; 
// };

// type BackendCalibrationItem = {
//   baseline: number;
//   min_range: number;
//   max_range: number;
// };

// type RangesResponse = {
//   ranges: Record<string, RangeData>;
//   samples_analyzed: number;
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

// const safeParseNumber = (val: number | string | null | undefined): string => {
//   if (val === null || val === undefined) return "0.00";
//   const num = Number(val);
//   return isNaN(num) ? "0.00" : num.toFixed(2);
// };

// export default function CalibrationPage() {
//   const [ranges, setRanges] = useState<Record<string, RangeData>>({});
//   const [latestParams, setLatestParams] = useState<Record<string, string>>({});
  
//   const [baselineSnapshot, setBaselineSnapshot] = useState<Record<string, string>>({});
//   const [baselineRanges, setBaselineRanges] = useState<
//     Record<string, { lower_tolerance: number; upper_tolerance: number }>
//   >({});
//   const [keyMap, setKeyMap] = useState<Record<string, string>>({});
  
//   const [selectedMachine, setSelectedMachine] = useState("UBE 850T-2");
//   const [selectedDie, setSelectedDie] = useState("S16"); 

//   const [isInitialLoading, setIsInitialLoading] = useState(true);
//   const [isCalculating, setIsCalculating] = useState(false);
//   const [isApplying, setIsApplying] = useState(false);
//   const [statusMessage, setStatusMessage] = useState("");
//   const [statusType, setStatusType] = useState<"success" | "error" | "">("");

//   const normalizeKey = useCallback((key: string): string => {
//     return key
//       .trim()
//       .toLowerCase()
//       .replaceAll("/", "_")
//       .replaceAll("-", "_")
//       .replaceAll(" ", "_");
//   }, []);

//   const fetchDatabaseLatest = useCallback(async () => {
//     try {
//       const res = await fetch(
//         `${base_api}/api/calibration/latest?machine=${encodeURIComponent(selectedMachine)}&die=${encodeURIComponent(selectedDie)}`,
//         { headers: { "ngrok-skip-browser-warning": "true" } }
//       );

//       const data = await res.json();
//       const formattedDb: Record<string, string> = {};
//       const toleranceRanges: Record<string, { lower_tolerance: number; upper_tolerance: number }> = {};
//       const mapping: Record<string, string> = {};

//       if (data && typeof data === "object" && !Array.isArray(data)) {
//         Object.entries(data).forEach(([k, v]) => {
//           const normalized = normalizeKey(k);
//           const value = v as BackendCalibrationItem;

//           formattedDb[normalized] = safeParseNumber(value?.baseline);
          
//           toleranceRanges[normalized] = {
//             lower_tolerance: value?.min_range ?? 0,
//             upper_tolerance: value?.max_range ?? 0,
//           };
          
//           mapping[normalized] = k;
//         });
//       }

//       setBaselineSnapshot(formattedDb);
//       setBaselineRanges(toleranceRanges);
//       setKeyMap(mapping);
//     } catch (err) {
//       console.error("Failed to fetch latest DB calibration", err);
//     }
//   }, [selectedMachine, selectedDie, normalizeKey]);

//   useEffect(() => {
//     const loadData = async () => {
//       setIsInitialLoading(true);
//       try {
//         await fetchDatabaseLatest();
//       } catch (err) {
//         console.error("Failed to load calibration data:", err);
//       } finally {
//         setIsInitialLoading(false);
//       }
//     };

//     loadData();
//   }, [selectedMachine, selectedDie, fetchDatabaseLatest]);

//   useEffect(() => {
//     const handleVisibility = async () => {
//       if (document.visibilityState === "visible") {
//         await fetchDatabaseLatest();
//       }
//     };

//     document.addEventListener("visibilitychange", handleVisibility);
//     return () => {
//       document.removeEventListener("visibilitychange", handleVisibility);
//     };
//   }, [fetchDatabaseLatest]);

//   const calculateCalibration = async () => {
//     setIsCalculating(true);
//     setStatusMessage("");
//     setStatusType("");
//     try {
//       const headers = { "ngrok-skip-browser-warning": "true" };
//       const res = await fetch(
//         `${base_api}/api/calibration/ranges?machine=${encodeURIComponent(selectedMachine)}&die=${encodeURIComponent(selectedDie)}`, 
//         { headers }
//       );
//       const data: RangesResponse = await res.json();
      
//       setRanges(data.ranges || {});

//       const mapping: Record<string, string> = { ...keyMap };
//       const mathInputs: Record<string, string> = {};

//       Object.entries(data.ranges || {}).forEach(([k, v]) => {
//         const normK = normalizeKey(k);
//         mapping[normK] = k;
//         mathInputs[normK] = safeParseNumber(v.baseline);
//       });

//       setKeyMap(mapping);
//       setLatestParams(mathInputs);
//       setStatusMessage("Calculated optimized windows successfully.");
//       setStatusType("success");
//     } catch (err) {
//       console.error("Failed to calculate ranges:", err);
//       setStatusMessage("Failed to calculate targeted calibration ranges.");
//       setStatusType("error");
//     } finally {
//       setIsCalculating(false);
//       setTimeout(() => setStatusMessage(""), 4000);
//     }
//   };

//   const machines = ["UBE 850T-1", "UBE 850T-2", "UBE 850T-3"];
//   const dies = ["S14", "S15", "S16"]; 
//   const bottomRows = useMemo(() => Object.entries(ranges), [ranges]);
//   const topRows = useMemo(() => Object.keys(baselineSnapshot), [baselineSnapshot]);

//   const handleChange = (key: string, value: string) => {
//     setLatestParams((prev) => ({
//       ...prev,
//       [key]: value,
//     }));
//   };

//   const buildPayload = () => {
//     const payload: Record<string, RangeData> = {};
//     bottomRows.forEach(([key, value]) => {
//       const normalizedKey = normalizeKey(key);
//       const backendKey = keyMap[normalizedKey] || key;

//       const finalValue =
//         latestParams[normalizedKey] !== undefined
//           ? Number(latestParams[normalizedKey])
//           : (value?.baseline ?? 0); 

//       payload[backendKey] = {
//         ...value,
//         baseline: finalValue,
//       };
//     });
//     return payload;
//   };

//   const applyCalibration = async () => {
//     setIsApplying(true);
//     setStatusMessage("");
//     setStatusType("");

//     try {
//       const payload = buildPayload();
//       const res = await fetch(
//         `${base_api}/api/calibration/apply?machine=${encodeURIComponent(selectedMachine)}&die=${encodeURIComponent(selectedDie)}`, 
//         {
//           method: "POST",
//           headers: { 
//             "Content-Type": "application/json",
//             "ngrok-skip-browser-warning": "true" 
//           },
//           body: JSON.stringify(payload),
//         }
//       );

//       if (!res.ok) {
//         const errBody = await res.json();
//         throw new Error(JSON.stringify(errBody));
//       }

//       const data = await res.json();
//       setStatusMessage(data.message || "Calibration Applied Successfully");
//       setStatusType("success");

//       await fetchDatabaseLatest();
//     } catch(err) {
//       console.error(err);
//       setStatusMessage("Failed to apply calibration");
//       setStatusType("error");
//     } finally {
//       setIsApplying(false);
//       setTimeout(() => setStatusMessage(""), 4000);
//     }
//   };

//   if (isInitialLoading) {
//     return (
//       <div className="bg-[#07111F] min-h-screen w-full flex items-center justify-center flex-col gap-4">
//         <div className="w-10 h-10 border-4 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin"></div>
//         <p className="text-cyan-400 font-semibold tracking-wide animate-pulse">Loading Latest Configuration...</p>
//       </div>
//     );
//   }

//   return (
//     <div className="bg-[#07111F] min-h-screen text-white w-full max-w-none px-6 md:px-12 py-8">
      
//       <div className="mb-8">
//         <h1 className="text-2xl md:text-[38px] font-bold leading-tight md:leading-none">Machine Calibration</h1>
//         <p className="text-gray-500 mt-2 text-sm md:text-base">
//           Zero-defect operating windows derived from historical production data
//         </p>
//       </div>

//       <div className="mb-6 flex flex-wrap gap-4 items-end justify-between">
//         <div className="flex flex-wrap gap-4">
//           <div className="w-full sm:w-56">
//             <div className="text-xs text-gray-500 mb-1.5 uppercase tracking-[2px]">Machine</div>
//             <select
//               value={selectedMachine}
//               onChange={(e) => setSelectedMachine(e.target.value)}
//               className="w-full bg-[#121B2B] border border-[#1F2937] rounded-lg px-4 py-3 text-sm text-white outline-none cursor-pointer"
//             >
//               {machines.map((machine) => (
//                 <option key={machine} value={machine}>
//                   {machine}
//                 </option>
//               ))}
//             </select>
//           </div>

//           <div className="w-full sm:w-56">
//             <div className="text-xs text-gray-500 mb-1.5 uppercase tracking-[2px]">Die</div>
//             <select
//               value={selectedDie}
//               onChange={(e) => setSelectedDie(e.target.value)}
//               className="w-full bg-[#121B2B] border border-[#1F2937] rounded-lg px-4 py-3 text-sm text-white outline-none cursor-pointer"
//             >
//               {dies.map((die) => (
//                 <option key={die} value={die}>
//                   {die}
//                 </option>
//               ))}
//             </select>
//           </div>
//         </div>

//         <button
//           onClick={calculateCalibration}
//           disabled={isCalculating || isApplying}
//           className={`
//             font-bold px-6 py-3 rounded-xl text-sm tracking-wide uppercase transition-colors
//             ${isCalculating 
//               ? "bg-purple-600/50 text-white/50 cursor-not-allowed"
//               : "bg-purple-600 hover:bg-purple-500 text-white shadow-[0_0_15px_rgba(147,51,234,0.2)]"
//             }
//           `}
//         >
//           {isCalculating ? "Calculating..." : "Calculate Calibration"}
//         </button>
//       </div>

//       <div className="mb-4 text-xl md:text-2xl font-semibold">Current Applied Calibration</div>

//       <div className="bg-[#121B2B] border border-[#1F2937] rounded-xl overflow-x-auto mb-10">
//         <div className="w-full min-w-[850px]">
//           <div className="hidden md:grid grid-cols-[4fr_3fr_5fr] gap-6 px-6 py-4 border-b border-[#1F2937] text-[11px] uppercase tracking-[2px] text-gray-500 items-center text-center w-full">
//             <div className="text-left">Parameter</div>
//             <div>Latest Snapshot Value</div>
//             <div>Tolerance Range</div>
//           </div>

//           {topRows.length === 0 ? (
//             <div className="text-center py-8 text-gray-500 text-sm">
//               No latest calibration found for this machine/die combination.
//             </div>
//           ) : (
//             topRows.map((normalizedKey, index) => {
//               const presentationKey = keyMap[normalizedKey] || normalizedKey.toUpperCase().replaceAll("_", " ");
//               const unit = getUnit(presentationKey);
//               const snapshotValue = baselineSnapshot[normalizedKey] || "0.00";
//               const tolerance = baselineRanges[normalizedKey];

//               return (
//                 <div
//                   key={index}
//                   className="flex flex-col md:grid md:grid-cols-[4fr_3fr_5fr] gap-6 px-6 py-5 border-b border-[#182232] items-center text-center hover:bg-[#0D1625] transition-all w-full"
//                 >
//                   <div className="text-left w-full">
//                     <div className="text-white text-base font-semibold break-words">{presentationKey}</div>
//                   </div>

//                   <div className="flex justify-between md:justify-center items-center w-full border-b border-gray-800/40 pb-2 md:pb-0 md:border-none">
//                     <span className="md:hidden text-xs text-gray-500 uppercase tracking-wider">Snapshot Value</span>
//                     <span className="text-cyan-400 font-bold text-base">
//                       {snapshotValue} {unit}
//                     </span>
//                   </div>

//                   <div className="w-full flex flex-col items-center justify-center gap-1">
//                     {tolerance ? (
//                       <span className="text-gray-300 font-semibold text-sm">
//                         {tolerance.lower_tolerance.toFixed(2)} – {tolerance.upper_tolerance.toFixed(2)} {unit}
//                       </span>
//                     ) : (
//                       <span className="text-gray-600 text-xs">—</span>
//                     )}
//                   </div>
//                 </div>
//               );
//             })
//           )}
//         </div>
//       </div>

//       <div className="bg-[#121B2B] border border-[#1F2937] rounded-xl p-5 md:p-8">
//         <h2 className="text-xl md:text-2xl font-semibold mb-6">Newly Corrected Recipe</h2>

//         {bottomRows.length === 0 ? (
//           <div className="text-center py-12 text-gray-500 border border-dashed border-gray-800 rounded-xl">
//             Click the <span className="text-purple-400 font-semibold">&quot;Calculate Calibration&quot;</span> button above to dynamically load operating profiles.
//           </div>
//         ) : (
//           <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
//             {bottomRows.map(([key, value], index) => {
//               const normalizedKey = normalizeKey(key);
//               const unit = value?.unit || getUnit(key);

//               const inputValue = latestParams[normalizedKey] || "0.00";
//               const snapshotValue = baselineSnapshot[normalizedKey] || "0.00";

//               return (
//                 <div
//                   key={index}
//                   className="bg-[#0B1320] border border-[#1F2937] rounded-xl p-5 flex flex-col justify-between"
//                 >
//                   <div>
//                     <div className="text-white text-base font-semibold mb-3 truncate" title={key}>
//                       {key}
//                     </div>

//                     <div className="flex justify-between text-xs mb-4">
//                       <div>
//                         <div className="text-gray-500">Lower Limit</div>
//                         <div className="text-green-400 font-semibold mt-0.5">
//                           {Number(value?.min_range ?? 0).toFixed(2)} {unit}
//                         </div>
//                       </div>

//                       <div className="text-right">
//                         <div className="text-gray-500">Upper Limit</div>
//                         <div className="text-red-400 font-semibold mt-0.5">
//                           {Number(value?.max_range ?? 0).toFixed(2)} {unit}
//                         </div>
//                       </div>
//                     </div>

//                     <div className="bg-[#121B2B] border border-[#1F2937]/60 rounded-lg p-2.5 mb-4 text-xs flex justify-between items-center">
//                       <div className="min-w-0 flex-1">
//                         <span className="text-gray-500 block text-[10px] uppercase tracking-wider">Before</span>
//                         <span className="text-gray-400 font-medium truncate block w-full">
//                           {snapshotValue} {unit}
//                         </span>
//                       </div>
//                       <div className="text-gray-600 font-bold px-3 flex-shrink-0">→</div>
//                       <div className="text-right min-w-0 flex-1">
//                         <span className="text-gray-500 block text-[10px] uppercase tracking-wider">After</span>
//                         <span className="text-cyan-400 font-semibold truncate block w-full">
//                           {!isNaN(Number(inputValue)) ? Number(inputValue).toFixed(2) : inputValue} {unit}
//                         </span>
//                       </div>
//                     </div>
//                   </div>

//                   <div className="relative mt-1">
//                     <input
//                       type="number"
//                       step="0.01"
//                       value={inputValue}
//                       onChange={(e) =>
//                         handleChange(normalizedKey, e.target.value)
//                       }
//                       className="w-full bg-[#07111F] border border-[#1F2937] rounded-lg px-4 py-3 pr-16 text-sm text-white outline-none focus:border-cyan-400"
//                     />

//                     {unit && (
//                       <span className="absolute right-4 top-3 text-gray-500 text-sm select-none">
//                         {unit}
//                       </span>
//                     )}
//                   </div>
//                 </div>
//               );
//             })}
//           </div>
//         )}

//         <div className="flex flex-col sm:flex-row justify-end items-center gap-4 mt-8 md:mt-10">
//           {statusMessage && (
//             <div
//               className={`px-4 py-2.5 rounded-lg text-sm font-semibold transition-all ${
//                 statusType === "success"
//                   ? "bg-green-500/10 text-green-400 border border-green-500/20"
//                   : "bg-red-500/10 text-red-400 border border-red-500/20"
//               }`}
//             >
//               {statusMessage}
//             </div>
//           )}

//           <button
//             onClick={applyCalibration}
//             disabled={isApplying || bottomRows.length === 0}
//             className={`
//               font-bold px-8 py-3.5 rounded-xl text-base tracking-wide uppercase transition-colors
//               ${isApplying || bottomRows.length === 0
//                   ? "bg-cyan-600/30 text-white/20 cursor-not-allowed"
//                   : "bg-cyan-500 hover:bg-cyan-400 text-black shadow-[0_0_15px_rgba(34,211,238,0.2)]"
//               }
//             `}
//           >
//             {isApplying ? "Applying..." : "Apply Calibration"}
//           </button>
//         </div>
//       </div>
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

type RangeData = {
  baseline: number;
  tolerance: number;
  min_range: number;
  max_range: number;
  unit?: string;
};

type BackendCalibrationItem = {
  baseline: number;
  min_range: number;
  max_range: number;
};

type RangesResponse = {
  ranges: Record<string, RangeData>;
  samples_analyzed: number;
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

const safeParseNumber = (val: number | string | null | undefined): string => {
  if (val === null || val === undefined) return "0.00";
  const num = Number(val);
  return isNaN(num) ? "0.00" : num.toFixed(2);
};

export default function CalibrationPage() {
  const [ranges, setRanges] = useState<Record<string, RangeData>>({});
  const [latestParams, setLatestParams] = useState<Record<string, string>>({});
  const [isCalculated, setIsCalculated] = useState(false); // New toggle state
  
  const [baselineSnapshot, setBaselineSnapshot] = useState<Record<string, string>>({});
  const [baselineRanges, setBaselineRanges] = useState<
    Record<string, { lower_tolerance: number; upper_tolerance: number }>
  >({});
  const [keyMap, setKeyMap] = useState<Record<string, string>>({});
  
  const [selectedMachine, setSelectedMachine] = useState("UBE 850T-2");
  const [selectedDie, setSelectedDie] = useState("S16");

  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [isCalculating, setIsCalculating] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [statusType, setStatusType] = useState<"success" | "error" | "">("");

  const normalizeKey = useCallback((key: string): string => {
    return key
      .trim()
      .toLowerCase()
      .replaceAll("/", "_")
      .replaceAll("-", "_")
      .replaceAll(" ", "_");
  }, []);

  const fetchDatabaseLatest = useCallback(async () => {
    try {
      const res = await fetch(
        `${base_api}/api/calibration/latest?machine=${encodeURIComponent(selectedMachine)}&die=${encodeURIComponent(selectedDie)}`,
        { headers: { "ngrok-skip-browser-warning": "true" } }
      );

      
      const data = await res.json();
      
      const initialRanges: Record<string, RangeData> = {};
      const formattedSnapshot: Record<string, string> = {};
      const toleranceRanges: Record<string, { lower_tolerance: number; upper_tolerance: number }> = {};
      const mapping: Record<string, string> = {};

      if (data && typeof data === "object" && !Array.isArray(data)) {
        Object.entries(data).forEach(([k, v]) => {
          const normalized = normalizeKey(k);
          const value = v as BackendCalibrationItem;
          
          initialRanges[k] = {
            baseline: value.baseline,
            min_range: value.min_range,
            max_range: value.max_range,
            tolerance: 0
          };
          
          formattedSnapshot[normalized] = safeParseNumber(value.baseline);
          toleranceRanges[normalized] = {
            lower_tolerance: value.min_range,
            upper_tolerance: value.max_range,
          };
          mapping[normalized] = k;
        });
      }

      setRanges(initialRanges);
      setBaselineSnapshot(formattedSnapshot);
      setBaselineRanges(toleranceRanges);
      setKeyMap(mapping);
      setIsCalculated(false); // Reset toggle when fetching latest
    } catch (err) {
      console.error("Failed to fetch latest DB calibration", err);
    }
  }, [selectedMachine, selectedDie, normalizeKey]);

  useEffect(() => {
    const loadData = async () => {
      setIsInitialLoading(true);
      await fetchDatabaseLatest();
      setIsInitialLoading(false);
    };
    loadData();
  }, [selectedMachine, selectedDie, fetchDatabaseLatest]);

  const calculateCalibration = async () => {
    setIsCalculating(true);
    setStatusMessage("");
    try {
      const res = await fetch(
        `${base_api}/api/calibration/ranges?machine=${encodeURIComponent(selectedMachine)}&die=${encodeURIComponent(selectedDie)}`,
        { headers: { "ngrok-skip-browser-warning": "true" } }
      );
      const data: RangesResponse = await res.json();
      
      setRanges(data.ranges || {});
      const mathInputs: Record<string, string> = {};
      Object.entries(data.ranges || {}).forEach(([k, v]) => {
        mathInputs[normalizeKey(k)] = safeParseNumber(v.baseline);
      });
      setLatestParams(mathInputs);
      setIsCalculated(true); // Enable calculated view

      setStatusMessage("Calculated optimized windows successfully.");
      setStatusType("success");
    } catch (err) {
      setStatusMessage("Failed to calculate targeted calibration ranges.");
      setStatusType("error");
    } finally {
      setIsCalculating(false);
      setTimeout(() => setStatusMessage(""), 4000);
    }
  };

  const machines = ["UBE 850T-1", "UBE 850T-2", "UBE 850T-3"];
  const dies = ["S14", "S15", "S16"];
  const calculatedRows = useMemo(() => Object.entries(ranges), [ranges]);

  const handleChange = (key: string, value: string) => {
    setLatestParams((prev) => ({ ...prev, [key]: value }));
  };

  const buildPayload = () => {
    const payload: Record<string, RangeData> = {};
    calculatedRows.forEach(([key, value]) => {
      const normalizedKey = normalizeKey(key);
      const backendKey = keyMap[normalizedKey] || key;
      const finalValue = latestParams[normalizedKey] !== undefined ? Number(latestParams[normalizedKey]) : (value?.baseline ?? 0);
      payload[backendKey] = { ...value, baseline: finalValue };
    });
    return payload;
  };

  const applyCalibration = async () => {
    setIsApplying(true);
    try {
      const res = await fetch(
        `${base_api}/api/calibration/apply?machine=${encodeURIComponent(selectedMachine)}&die=${encodeURIComponent(selectedDie)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json", "ngrok-skip-browser-warning": "true" },
          body: JSON.stringify(buildPayload()),
        }
      );
      if (!res.ok) throw new Error();
      const data = await res.json();
      setStatusMessage(data.message || "Calibration Applied Successfully");
      setStatusType("success");
      await fetchDatabaseLatest();
    } catch {
      setStatusMessage("Failed to apply calibration");
      setStatusType("error");
    } finally {
      setIsApplying(false);
      setTimeout(() => setStatusMessage(""), 4000);
    }
  };

  if (isInitialLoading) {
    return (
      <div className="bg-[#07111F] min-h-screen w-full flex items-center justify-center flex-col gap-4">
        <div className="w-10 h-10 border-4 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin"></div>
        <p className="text-cyan-400 font-semibold tracking-wide animate-pulse">Loading Latest Configuration...</p>
      </div>
    );
  }

  return (
    <div className="bg-[#07111F] min-h-screen text-white w-full max-w-none px-6 md:px-12 py-8">
      <div className="mb-8">
        <h1 className="text-2xl md:text-[38px] font-bold">Machine Calibration</h1>
      </div>
      <div className="mb-8 flex flex-wrap gap-4 items-end justify-between">
        <div className="flex flex-wrap gap-4">
          <select value={selectedMachine} onChange={(e) => setSelectedMachine(e.target.value)} className="bg-[#121B2B] border border-[#1F2937] rounded-lg px-4 py-3 text-sm outline-none cursor-pointer">
            {machines.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <select value={selectedDie} onChange={(e) => setSelectedDie(e.target.value)} className="bg-[#121B2B] border border-[#1F2937] rounded-lg px-4 py-3 text-sm outline-none cursor-pointer">
            {dies.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
        <button onClick={calculateCalibration} disabled={isCalculating || isApplying} className="bg-purple-600 px-6 py-3 rounded-xl text-sm font-bold uppercase hover:bg-purple-500 transition-colors">
          {isCalculating ? "Calculating..." : "Calculate Calibration"}
        </button>
      </div>
      <div className="bg-[#121B2B] border border-[#1F2937] rounded-xl p-5 md:p-8">
        <h2 className="text-xl md:text-2xl font-semibold mb-6">Recipe Window Optimization</h2>
        {calculatedRows.length === 0 ? (
          <div className="text-center py-12 text-gray-500 border border-dashed border-gray-800 rounded-xl">No configuration data available.</div>
        ) : (
          <div className="w-full overflow-x-auto min-w-[800px]">
            <div className="grid grid-cols-[4fr_4fr_4fr] gap-4 px-4 py-3 border-b border-[#1F2937] text-xs font-bold uppercase text-gray-400">
              <div>Parameter</div>
              <div className="text-center bg-[#182335] py-1.5 rounded-md">Current</div>
              <div className="text-center bg-[#1e1c3a] py-1.5 rounded-md text-purple-300">Calculated</div>
            </div>
            {calculatedRows.map(([key, value], index) => {
              const norm = normalizeKey(key);
              const unit = value?.unit || getUnit(key);
              return (
                <div key={index} className="grid grid-cols-[4fr_4fr_4fr] gap-4 px-4 py-5 border-b border-[#182232] items-center">
                  <div><div className="text-base font-bold">{key}</div>{unit && <span className="text-xs text-gray-500">Unit: {unit}</span>}</div>
                  <div className="space-y-1 text-sm border-r border-gray-800 pr-2">
                    <div className="flex justify-between"><span className="text-gray-500">Baseline:</span><span className="text-cyan-400 font-semibold">{baselineSnapshot[norm] || "0.00"}</span></div>
                    <div className="flex justify-between"><span className="text-gray-500">Lower:</span><span className="text-green-400 font-medium">{baselineRanges[norm]?.lower_tolerance.toFixed(2) || "0.00"}</span></div>
                    <div className="flex justify-between"><span className="text-gray-500">Upper:</span><span className="text-red-400 font-medium">{baselineRanges[norm]?.upper_tolerance.toFixed(2) || "0.00"}</span></div>
                  </div>
                  <div className="space-y-1 text-sm pl-2">
                    <div className="flex justify-between items-center"><span className="text-gray-500">Target:</span>
                      <input type="number" value={isCalculated ? (latestParams[norm] ?? "") : ""}  onChange={(e) => handleChange(norm, e.target.value)} className="w-24 bg-[#07111F] border border-[#1F2937] rounded px-2 text-right outline-none focus:border-cyan-400" />
                    </div>
                    <div className="flex justify-between"><span className="text-gray-500">Lower:</span><span className="text-green-400 font-semibold">{isCalculated ? value.min_range.toFixed(2) : "0.00"} {unit}</span></div>
                    <div className="flex justify-between"><span className="text-gray-500">Upper:</span><span className="text-red-400 font-semibold">{isCalculated ? value.max_range.toFixed(2) : "0.00"} {unit}</span></div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        <div className="flex justify-end gap-4 mt-8">
          {statusMessage && <div className={`px-4 py-2 rounded-lg text-sm ${statusType === "success" ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"}`}>{statusMessage}</div>}
          <button onClick={applyCalibration} disabled={isApplying || calculatedRows.length === 0} className="bg-cyan-500 px-8 py-3 rounded-xl font-bold text-black uppercase hover:bg-cyan-400 disabled:opacity-20 transition-colors">
            {isApplying ? "Applying..." : "Apply Calibration"}
          </button>
        </div>
      </div>
    </div>
  );
}