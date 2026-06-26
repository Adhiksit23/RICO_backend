// "use client";

// import {
//   useEffect,
//   useMemo,
//   useState,
//   useCallback,
// } from "react";

// // Use environment variable with a fallback for local testing
// const base_api = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

// type SummaryData = {
//   samples_analyzed: number;
// };

// type RangeData = {
//   baseline: number;
//   tolerance: number;
//   min_range: number;
//   max_range: number;
//   unit?: string; // Newly added to support backend-provided units
// };

// type RangesResponse = {
//   ranges: Record<string, RangeData>;
//   samples_analyzed: number;
// };

// // Fallback unit parser if the backend hasn't provided the 'unit' field yet
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
//   // ---- STATE: Data ----
//   const [summary, setSummary] = useState<SummaryData>({ samples_analyzed: 0 });
//   const [ranges, setRanges] = useState<Record<string, RangeData>>({});
//   const [latestParams, setLatestParams] = useState<Record<string, string>>({});
//   const [baselineSnapshot, setBaselineSnapshot] = useState<Record<string, string>>({});
//   const [keyMap, setKeyMap] = useState<Record<string, string>>({});
  
//   // ---- STATE: Filters ----
//   const [selectedMachine, setSelectedMachine] = useState("DC-01");
//   const [selectedDie, setSelectedDie] = useState("S14"); // Fixed Format

//   // ---- STATE: UI & Loading ----
//   const [isInitialLoading, setIsInitialLoading] = useState(true);
//   const [isApplying, setIsApplying] = useState(false);
//   const [statusMessage, setStatusMessage] = useState("");
//   const [statusType, setStatusType] = useState<"success" | "error" | "">("");

//   // ---------------- HELPERS ----------------

//   const normalizeKey = useCallback((key: string): string => {
//     return key
//       .trim()
//       .toLowerCase()
//       .replaceAll("/", "_")
//       .replaceAll("-", "_")
//       .replaceAll(" ", "_");
//   }, []);

//   // ---------------- FETCHING ----------------

//   const fetchLatest = useCallback(async (updateBaseline = false) => {
//     try {
//       const res = await fetch(
//         `${base_api}/api/calibration/latest?machine=${encodeURIComponent(selectedMachine)}&die=${encodeURIComponent(selectedDie)}`,
//         { headers: { "ngrok-skip-browser-warning": "true" } }
//       );

//       const data = await res.json();
//       const formatted: Record<string, string> = {};
//       const mapping: Record<string, string> = {};

//       Object.entries(data).forEach(([k, v]) => {
//         const normalized = normalizeKey(k);
//         // Safely handle potentially null values from latest
//         formatted[normalized] = v !== null ? Number(v).toFixed(2) : "0.00";
//         mapping[normalized] = k;
//       });

//       setLatestParams(formatted);
//       setKeyMap(mapping);

//       if (updateBaseline) {
//         setBaselineSnapshot(formatted);
//       }
//     } catch (err) {
//       console.error("Failed to fetch latest calibration", err);
//     }
//   }, [selectedMachine, selectedDie, normalizeKey]);

//   // Initial Load & Dropdown Changes
//   useEffect(() => {
//     const loadData = async () => {
//       setIsInitialLoading(true);
//       try {
//         const headers = { "ngrok-skip-browser-warning": "true" };
        
//         // Fetch combined ranges and samples_analyzed data
//         await fetch(`${base_api}/api/calibration/ranges?machine=${encodeURIComponent(selectedMachine)}&die=${encodeURIComponent(selectedDie)}`, { headers })
//           .then((res) => res.json())
//           .then((data: RangesResponse) => {
//             setRanges(data.ranges || {});
//             setSummary({
//               samples_analyzed: data.samples_analyzed || 0,
//             });
//           })
//           .catch(console.error);

//         // Fetch latest and explicitly sync the baseline snapshot since machine/die changed
//         await fetchLatest(true);
//       } finally {
//         setIsInitialLoading(false);
//       }
//     };

//     loadData();
//   }, [selectedMachine, selectedDie, fetchLatest]);

//   // Tab Visibility Refresh
//   useEffect(() => {
//     const handleVisibility = async () => {
//       if (document.visibilityState === "visible") {
//         await fetchLatest(false);
//       }
//     };

//     document.addEventListener("visibilitychange", handleVisibility);
//     return () => {
//       document.removeEventListener("visibilitychange", handleVisibility);
//     };
//   }, [fetchLatest]);

//   // ---------------- DROPDOWNS & MEMO ----------------

//   const machines = ["DC-01", "DC-02", "DC-03"];
//   const dies = ["S14", "S15", "S16"]; // Fixed Format
//   const rows = useMemo(() => Object.entries(ranges), [ranges]);
//   console.log(rows)

//   const handleChange = (key: string, value: string) => {
//     setLatestParams((prev) => ({
//       ...prev,
//       [key]: value,
//     }));
//   };

//   // ---------------- ACTIONS (APPLY) ----------------

//   const buildPayload = () => {
//     const payload: Record<string, number> = {};
//     rows.forEach(([key, value]) => {
//       const normalizedKey = normalizeKey(key);
//       const backendKey = keyMap[normalizedKey] || key;

//       const finalValue =
//         latestParams[normalizedKey] !== undefined
//           ? Number(latestParams[normalizedKey])
//           : (value?.baseline ?? 0); // Safe fallback

//       payload[backendKey] = finalValue;
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
//           headers: { "Content-Type": "application/json" },
//           body: JSON.stringify(payload),
//         }
//       );

//       if (!res.ok) throw new Error("Failed to apply");

//       const data = await res.json();
//       setStatusMessage(data.message || "Calibration Applied Successfully");
//       setStatusType("success");

//       // Refetch latest AND update the 'Before' snapshot to our new values
//       await fetchLatest(true);
//     } catch {
//       setStatusMessage("Failed to apply calibration");
//       setStatusType("error");
//     } finally {
//       setIsApplying(false);
//       setTimeout(() => {
//         setStatusMessage("");
//       }, 4000);
//     }
//   };

//   // ---------------- RENDER ----------------

//   if (isInitialLoading) {
//     return (
//       <div className="bg-[#07111F] min-h-screen w-full flex items-center justify-center flex-col gap-4">
//         <div className="w-10 h-10 border-4 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin"></div>
//         <p className="text-cyan-400 font-semibold tracking-wide animate-pulse">Loading calibration data...</p>
//       </div>
//     );
//   }

//   return (
//     <div className="bg-[#07111F] min-h-screen text-white w-full max-w-none px-6 md:px-12 py-8">
      
//       {/* HEADER */}
//       <div className="mb-8">
//         <h1 className="text-2xl md:text-[38px] font-bold leading-tight md:leading-none">Machine Calibration</h1>
//         <p className="text-gray-500 mt-2 text-sm md:text-base">
//           Zero-defect operating windows derived from historical production data
//         </p>
//       </div>

//       {/* SUMMARY STATS - Single Card */}
//       <div className="mb-6">
//         <div className="bg-[#121B2B] border border-[#1F2937] rounded-xl p-5 md:p-6 shadow-sm inline-block min-w-[250px]">
//           <div className="text-[11px] uppercase tracking-[2px] text-gray-500 mb-1.5">Samples Analyzed</div>
//           <div className="text-white text-3xl font-bold">
//             {summary.samples_analyzed.toLocaleString()}
//           </div>
//         </div>
//       </div>

//       {/* FILTERS */}
//       <div className="flex flex-wrap gap-4 mb-10">
//         <div className="w-full sm:w-56">
//           <div className="text-xs text-gray-500 mb-1.5 uppercase tracking-[2px]">Machine</div>
//           <select
//             value={selectedMachine}
//             onChange={(e) => setSelectedMachine(e.target.value)}
//             className="w-full bg-[#121B2B] border border-[#1F2937] rounded-lg px-4 py-3 text-sm text-white outline-none cursor-pointer"
//           >
//             {machines.map((machine) => (
//               <option key={machine} value={machine}>
//                 {machine}
//               </option>
//             ))}
//           </select>
//         </div>

//         <div className="w-full sm:w-56">
//           <div className="text-xs text-gray-500 mb-1.5 uppercase tracking-[2px]">Die</div>
//           <select
//             value={selectedDie}
//             onChange={(e) => setSelectedDie(e.target.value)}
//             className="w-full bg-[#121B2B] border border-[#1F2937] rounded-lg px-4 py-3 text-sm text-white outline-none cursor-pointer"
//           >
//             {dies.map((die) => (
//               <option key={die} value={die}>
//                 {die}
//               </option>
//             ))}
//           </select>
//         </div>
//       </div>

//       <div className="mb-4 text-xl md:text-2xl font-semibold">Current Applied Calibration</div>

//       {/* TABLE */}
//       <div className="bg-[#121B2B] border border-[#1F2937] rounded-xl overflow-x-auto mb-10">
//         <div className="w-full min-w-[850px]">
//           <div className="hidden md:grid grid-cols-[3.5fr_2fr_2fr_1.5fr_4fr] gap-6 px-6 py-4 border-b border-[#1F2937] text-[11px] uppercase tracking-[2px] text-gray-500 items-center text-center w-full">
//             <div className="text-left">Parameter</div>
//             <div>Current Applied</div>
//             <div>Optimal Range</div>
//             <div>Std Dev</div>
//             <div>Comparison</div>
//           </div>

//           {rows.map(([key, value], index) => {
//             const normalizedKey = normalizeKey(key);
//             // Use backend unit if provided, otherwise fallback to guessing from the key name
//             const unit = value?.unit || getUnit(key);

//             const currentValue =
//             latestParams[normalizedKey] !== undefined
//             ? Number(latestParams[normalizedKey]): "NO DB DATA";
//             console.log(currentValue)

//             const snapshotValue = baselineSnapshot[normalizedKey];
//             console.log(snapshotValue)

//             return (
//               <div
//                 key={index}
//                 className="flex flex-col md:grid md:grid-cols-[3.5fr_2fr_2fr_1.5fr_4fr] gap-6 px-6 py-5 border-b border-[#182232] items-center text-center hover:bg-[#0D1625] transition-all w-full"
//               >
//                 {/* Parameter Block */}
//                 <div className="text-left w-full">
//                   <div className="text-white text-base font-semibold break-words">{key}</div>
//                   <div className="text-gray-500 text-xs mt-1">
//                     {/* Protected against undefined value objects */}
//                     Tol: {Number(value?.min_range ?? 0).toFixed(2)} - {Number(value?.max_range ?? 0).toFixed(2)} {unit}
//                   </div>
//                 </div>

//                 {/* Current Applied Column */}
//                 <div className="flex justify-between md:justify-center items-center w-full border-b border-gray-800/40 pb-2 md:pb-0 md:border-none">
//                   <span className="md:hidden text-xs text-gray-500 uppercase tracking-wider">Current Applied</span>
//                   <span className="text-cyan-400 font-semibold text-base">
//                     {currentValue.toFixed(2)} {unit}
//                   </span>
//                 </div>

//                 {/* Optimal Range Column */}
//                 <div className="flex justify-between md:justify-center items-center w-full border-b border-gray-800/40 pb-2 md:pb-0 md:border-none">
//                   <span className="md:hidden text-xs text-gray-500 uppercase tracking-wider">Optimal Range</span>
//                   <span className="text-green-400 text-base">
//                     {Number(value?.min_range ?? 0).toFixed(2)} - {Number(value?.max_range ?? 0).toFixed(2)} {unit}
//                   </span>
//                 </div>

//                 {/* Std Dev Column */}
//                 <div className="flex justify-between md:justify-center items-center w-full border-b border-gray-800/40 pb-2 md:pb-0 md:border-none">
//                   <span className="md:hidden text-xs text-gray-500 uppercase tracking-wider">Std Dev</span>
//                   <span className="text-gray-400 text-sm">
//                     ±{Number(value?.tolerance ?? 0).toFixed(2)} {unit}
//                   </span>
//                 </div>

//                 {/* Horizontal Comparison Pill */}
//                 <div className="w-full flex justify-center">
//                   <div className="bg-[#0F172A] border border-[#1F2937] rounded-lg px-4 py-2.5 flex items-center justify-between w-full shadow-inner gap-3 overflow-hidden">
//                     <div className="flex flex-col items-start min-w-0 flex-1">
//                       <span className="text-[9px] text-gray-500 uppercase tracking-wider font-semibold">Before</span>
//                       <span className="text-gray-300 text-xs mt-0.5 truncate w-full text-left">
//                         {snapshotValue ? `${snapshotValue} ${unit}` : "—"}
//                       </span>
//                     </div>
//                     <span className="text-cyan-500/50 text-sm flex-shrink-0 px-2">→</span>
//                     <div className="flex flex-col items-end min-w-0 flex-1">
//                       <span className="text-[9px] text-cyan-500 uppercase tracking-wider font-semibold">Current</span>
//                       <span className="text-cyan-400 text-sm font-bold mt-0.5 truncate w-full text-right">
//                         {currentValue.toFixed(2)} {unit}
//                       </span>
//                     </div>
//                   </div>
//                 </div>
//               </div>
//             );
//           })}
//         </div>
//       </div>

//       {/* NEWLY CORRECTED RECIPE */}
//       <div className="bg-[#121B2B] border border-[#1F2937] rounded-xl p-5 md:p-8">
//         <h2 className="text-xl md:text-2xl font-semibold mb-6">Newly Corrected Recipe</h2>

//         <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
//           {rows.map(([key, value], index) => {
//             const normalizedKey = normalizeKey(key);
//             const unit = value?.unit || getUnit(key);

//             const inputValue =
//               latestParams[normalizedKey] !== undefined
//                 ? latestParams[normalizedKey]
//                 : (value?.baseline ? Number(value.baseline).toFixed(2) : "0.00");

//             const snapshotValue = baselineSnapshot[normalizedKey] || (value?.baseline ? Number(value.baseline).toFixed(2) : "0.00");

//             return (
//               <div
//                 key={index}
//                 className="bg-[#0B1320] border border-[#1F2937] rounded-xl p-5 flex flex-col justify-between"
//               >
//                 <div>
//                   <div className="text-white text-base font-semibold mb-3 truncate" title={key}>
//                     {key}
//                   </div>

//                   <div className="flex justify-between text-xs mb-4">
//                     <div>
//                       <div className="text-gray-500">Lower Limit</div>
//                       <div className="text-green-400 font-semibold mt-0.5">
//                         {Number(value?.min_range ?? 0).toFixed(2)} {unit}
//                       </div>
//                     </div>

//                     <div className="text-right">
//                       <div className="text-gray-500">Upper Limit</div>
//                       <div className="text-red-400 font-semibold mt-0.5">
//                         {Number(value?.max_range ?? 0).toFixed(2)} {unit}
//                       </div>
//                     </div>
//                   </div>

//                   {/* Before/After Comparison Block */}
//                   <div className="bg-[#121B2B] border border-[#1F2937]/60 rounded-lg p-2.5 mb-4 text-xs flex justify-between items-center">
//                     <div className="min-w-0 flex-1">
//                       <span className="text-gray-500 block text-[10px] uppercase tracking-wider">Before</span>
//                       <span className="text-gray-400 font-medium truncate block w-full">{snapshotValue} {unit}</span>
//                     </div>
//                     <div className="text-gray-600 font-bold px-3 flex-shrink-0">→</div>
//                     <div className="text-right min-w-0 flex-1">
//                       <span className="text-gray-500 block text-[10px] uppercase tracking-wider">After</span>
//                       <span className="text-cyan-400 font-semibold truncate block w-full">
//                         {!isNaN(Number(inputValue)) ? Number(inputValue).toFixed(2) : inputValue} {unit}
//                       </span>
//                     </div>
//                   </div>
//                 </div>

//                 <div className="relative mt-1">
//                   <input
//                     type="number"
//                     step="0.01"
//                     value={inputValue}
//                     onChange={(e) =>
//                       handleChange(normalizedKey, e.target.value)
//                     }
//                     className="w-full bg-[#07111F] border border-[#1F2937] rounded-lg px-4 py-3 pr-16 text-sm text-white outline-none focus:border-cyan-400"
//                   />

//                   {unit && (
//                     <span className="absolute right-4 top-3 text-gray-500 text-sm select-none">
//                       {unit}
//                     </span>
//                   )}
//                 </div>
//               </div>
//             );
//           })}
//         </div>

//         {/* BUTTON ACTIONS & TOAST GROUP */}
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
//             disabled={isApplying}
//             className={`
//               font-bold
//               px-8
//               py-3.5
//               rounded-xl
//               text-base
//               tracking-wide
//               uppercase
//               transition-colors
//               ${
//                 isApplying
//                   ? "bg-cyan-600/50 text-black/50 cursor-not-allowed"
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


// const base_api = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const base_api = "https://outspoken-pandemic-surfer.ngrok-free.dev";

type SummaryData = {
  samples_analyzed: number;
};

type RangeData = {
  baseline: number;
  tolerance: number;
  min_range: number;
  max_range: number;
  unit?: string; 
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

export default function CalibrationPage() {
  const [summary, setSummary] = useState<SummaryData>({ samples_analyzed: 0 });
  const [ranges, setRanges] = useState<Record<string, RangeData>>({});
  
  // Holds the FORM INPUTS and UI state (initialized exclusively with computed math)
  const [latestParams, setLatestParams] = useState<Record<string, string>>({});
  
  // Holds the DATABASE state (strictly used for the 'Before' snapshot)
  const [baselineSnapshot, setBaselineSnapshot] = useState<Record<string, string>>({});
  const [keyMap, setKeyMap] = useState<Record<string, string>>({});
  
  const [selectedMachine, setSelectedMachine] = useState("DC-01");
  const [selectedDie, setSelectedDie] = useState("S14"); 

  const [isInitialLoading, setIsInitialLoading] = useState(true);
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

  // Fetch from the DB -> This ONLY sets the Before snapshot now
  const fetchDatabaseLatest = useCallback(async () => {
    try {
      const res = await fetch(
        `${base_api}/api/calibration/latest?machine=${encodeURIComponent(selectedMachine)}&die=${encodeURIComponent(selectedDie)}`,
        { headers: { "ngrok-skip-browser-warning": "true" } }
      );

      const data = await res.json();
      const formattedDb: Record<string, string> = {};

      Object.entries(data).forEach(([k, v]) => {
        const normalized = normalizeKey(k);
        formattedDb[normalized] = v !== null ? Number(v).toFixed(2) : "0.00";
      });

      setBaselineSnapshot(formattedDb);
    } catch (err) {
      console.error("Failed to fetch latest DB calibration", err);
    }
  }, [selectedMachine, selectedDie, normalizeKey]);

  useEffect(() => {
    const loadData = async () => {
      setIsInitialLoading(true);
      try {
        const headers = { "ngrok-skip-browser-warning": "true" };
        
        // 1. Fetch the computed math
        const res = await fetch(`${base_api}/api/calibration/ranges?machine=${encodeURIComponent(selectedMachine)}&die=${encodeURIComponent(selectedDie)}`, { headers });
        const data: RangesResponse = await res.json();
        
        setRanges(data.ranges || {});
        setSummary({ samples_analyzed: data.samples_analyzed || 0 });

        const mapping: Record<string, string> = {};
        const mathInputs: Record<string, string> = {};

        // 2. Pre-fill the input fields completely with the computed math
        Object.entries(data.ranges || {}).forEach(([k, v]) => {
          const normK = normalizeKey(k);
          mapping[normK] = k;
          mathInputs[normK] = Number(v.baseline).toFixed(2);
        });

        setKeyMap(mapping);
        setLatestParams(mathInputs);

        // 3. Fetch the DB to populate the Before column
        await fetchDatabaseLatest();
      } catch (err) {
        console.error("Failed to load calibration data:", err);
      } finally {
        setIsInitialLoading(false);
      }
    };

    loadData();
  }, [selectedMachine, selectedDie, fetchDatabaseLatest, normalizeKey]);

  useEffect(() => {
    const handleVisibility = async () => {
      if (document.visibilityState === "visible") {
        await fetchDatabaseLatest();
      }
    };

    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [fetchDatabaseLatest]);

  const machines = ["DC-01", "DC-02", "DC-03"];
  const dies = ["S14", "S15", "S16"]; 
  const rows = useMemo(() => Object.entries(ranges), [ranges]);

  const handleChange = (key: string, value: string) => {
    setLatestParams((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const buildPayload = () => {
    const payload: Record<string, number> = {};
    rows.forEach(([key, value]) => {
      const normalizedKey = normalizeKey(key);
      const backendKey = keyMap[normalizedKey] || key;

      const finalValue =
        latestParams[normalizedKey] !== undefined
          ? Number(latestParams[normalizedKey])
          : (value?.baseline ?? 0); 

      payload[backendKey] = finalValue;
    });
    return payload;
  };

  const applyCalibration = async () => {
    setIsApplying(true);
    setStatusMessage("");
    setStatusType("");

    try {
      const payload = buildPayload();
      const res = await fetch(
        `${base_api}/api/calibration/apply?machine=${encodeURIComponent(selectedMachine)}&die=${encodeURIComponent(selectedDie)}`, 
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );

      if (!res.ok) throw new Error("Failed to apply");

      const data = await res.json();
      setStatusMessage(data.message || "Calibration Applied Successfully");
      setStatusType("success");

      // Refetch the database to push the newly saved values into the "Before" snapshot
      await fetchDatabaseLatest();
    } catch {
      setStatusMessage("Failed to apply calibration");
      setStatusType("error");
    } finally {
      setIsApplying(false);
      setTimeout(() => {
        setStatusMessage("");
      }, 4000);
    }
  };

  if (isInitialLoading) {
    return (
      <div className="bg-[#07111F] min-h-screen w-full flex items-center justify-center flex-col gap-4">
        <div className="w-10 h-10 border-4 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin"></div>
        <p className="text-cyan-400 font-semibold tracking-wide animate-pulse">Computing Calibrations...</p>
      </div>
    );
  }

  return (
    <div className="bg-[#07111F] min-h-screen text-white w-full max-w-none px-6 md:px-12 py-8">
      
      <div className="mb-8">
        <h1 className="text-2xl md:text-[38px] font-bold leading-tight md:leading-none">Machine Calibration</h1>
        <p className="text-gray-500 mt-2 text-sm md:text-base">
          Zero-defect operating windows derived from historical production data
        </p>
      </div>

      <div className="mb-6">
        <div className="bg-[#121B2B] border border-[#1F2937] rounded-xl p-5 md:p-6 shadow-sm inline-block min-w-[250px]">
          <div className="text-[11px] uppercase tracking-[2px] text-gray-500 mb-1.5">Samples Analyzed</div>
          <div className="text-white text-3xl font-bold">
            {summary.samples_analyzed.toLocaleString()}
          </div>
        </div>
      </div>

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

      <div className="bg-[#121B2B] border border-[#1F2937] rounded-xl overflow-x-auto mb-10">
        <div className="w-full min-w-[850px]">
          <div className="hidden md:grid grid-cols-[3.5fr_2fr_2fr_1.5fr_4fr] gap-6 px-6 py-4 border-b border-[#1F2937] text-[11px] uppercase tracking-[2px] text-gray-500 items-center text-center w-full">
            <div className="text-left">Parameter</div>
            <div>Current Calculated</div>
            <div>Optimal Range</div>
            <div>Std Dev</div>
            <div>Comparison</div>
          </div>

          {rows.map(([key, value], index) => {
            const normalizedKey = normalizeKey(key);
            const unit = value?.unit || getUnit(key);

            const currentValue = latestParams[normalizedKey] || "0.00";
            const snapshotValue = baselineSnapshot[normalizedKey];

            return (
              <div
                key={index}
                className="flex flex-col md:grid md:grid-cols-[3.5fr_2fr_2fr_1.5fr_4fr] gap-6 px-6 py-5 border-b border-[#182232] items-center text-center hover:bg-[#0D1625] transition-all w-full"
              >
                <div className="text-left w-full">
                  <div className="text-white text-base font-semibold break-words">{key}</div>
                  <div className="text-gray-500 text-xs mt-1">
                    Tol: {Number(value?.min_range ?? 0).toFixed(2)} - {Number(value?.max_range ?? 0).toFixed(2)} {unit}
                  </div>
                </div>

                <div className="flex justify-between md:justify-center items-center w-full border-b border-gray-800/40 pb-2 md:pb-0 md:border-none">
                  <span className="md:hidden text-xs text-gray-500 uppercase tracking-wider">Current Calculated</span>
                  <span className="text-cyan-400 font-semibold text-base">
                    {currentValue} {unit}
                  </span>
                </div>

                <div className="flex justify-between md:justify-center items-center w-full border-b border-gray-800/40 pb-2 md:pb-0 md:border-none">
                  <span className="md:hidden text-xs text-gray-500 uppercase tracking-wider">Optimal Range</span>
                  <span className="text-green-400 text-base">
                    {Number(value?.min_range ?? 0).toFixed(2)} - {Number(value?.max_range ?? 0).toFixed(2)} {unit}
                  </span>
                </div>

                <div className="flex justify-between md:justify-center items-center w-full border-b border-gray-800/40 pb-2 md:pb-0 md:border-none">
                  <span className="md:hidden text-xs text-gray-500 uppercase tracking-wider">Std Dev</span>
                  <span className="text-gray-400 text-sm">
                    ±{Number(value?.tolerance ?? 0).toFixed(2)} {unit}
                  </span>
                </div>

                <div className="w-full flex justify-center">
                  <div className="bg-[#0F172A] border border-[#1F2937] rounded-lg px-4 py-2.5 flex items-center justify-between w-full shadow-inner gap-3 overflow-hidden">
                    <div className="flex flex-col items-start min-w-0 flex-1">
                      <span className="text-[9px] text-gray-500 uppercase tracking-wider font-semibold">Before</span>
                      <span className="text-gray-300 text-xs mt-0.5 truncate w-full text-left">
                        {snapshotValue ? `${snapshotValue} ${unit}` : "—"}
                      </span>
                    </div>
                    <span className="text-cyan-500/50 text-sm flex-shrink-0 px-2">→</span>
                    <div className="flex flex-col items-end min-w-0 flex-1">
                      <span className="text-[9px] text-cyan-500 uppercase tracking-wider font-semibold">Calculated</span>
                      <span className="text-cyan-400 text-sm font-bold mt-0.5 truncate w-full text-right">
                        {currentValue} {unit}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="bg-[#121B2B] border border-[#1F2937] rounded-xl p-5 md:p-8">
        <h2 className="text-xl md:text-2xl font-semibold mb-6">Newly Corrected Recipe</h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {rows.map(([key, value], index) => {
            const normalizedKey = normalizeKey(key);
            const unit = value?.unit || getUnit(key);

            const inputValue = latestParams[normalizedKey] || "0.00";
            const snapshotValue = baselineSnapshot[normalizedKey] || "—";

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
                        {Number(value?.min_range ?? 0).toFixed(2)} {unit}
                      </div>
                    </div>

                    <div className="text-right">
                      <div className="text-gray-500">Upper Limit</div>
                      <div className="text-red-400 font-semibold mt-0.5">
                        {Number(value?.max_range ?? 0).toFixed(2)} {unit}
                      </div>
                    </div>
                  </div>

                  <div className="bg-[#121B2B] border border-[#1F2937]/60 rounded-lg p-2.5 mb-4 text-xs flex justify-between items-center">
                    <div className="min-w-0 flex-1">
                      <span className="text-gray-500 block text-[10px] uppercase tracking-wider">Before</span>
                      <span className="text-gray-400 font-medium truncate block w-full">{snapshotValue} {snapshotValue !== "—" ? unit : ""}</span>
                    </div>
                    <div className="text-gray-600 font-bold px-3 flex-shrink-0">→</div>
                    <div className="text-right min-w-0 flex-1">
                      <span className="text-gray-500 block text-[10px] uppercase tracking-wider">After</span>
                      <span className="text-cyan-400 font-semibold truncate block w-full">
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

        <div className="flex flex-col sm:flex-row justify-end items-center gap-4 mt-8 md:mt-10">
          {statusMessage && (
            <div
              className={`px-4 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                statusType === "success"
                  ? "bg-green-500/10 text-green-400 border border-green-500/20"
                  : "bg-red-500/10 text-red-400 border border-red-500/20"
              }`}
            >
              {statusMessage}
            </div>
          )}

          <button
            onClick={applyCalibration}
            disabled={isApplying}
            className={`
              font-bold
              px-8
              py-3.5
              rounded-xl
              text-base
              tracking-wide
              uppercase
              transition-colors
              ${
                isApplying
                  ? "bg-cyan-600/50 text-black/50 cursor-not-allowed"
                  : "bg-cyan-500 hover:bg-cyan-400 text-black shadow-[0_0_15px_rgba(34,211,238,0.2)]"
              }
            `}
          >
            {isApplying ? "Applying..." : "Apply Calibration"}
          </button>
        </div>
      </div>
    </div>
  );
}