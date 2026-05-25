// "use client";
// import { useEffect, useMemo, useState } from "react";


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

// const parameterUnits: Record<string, string> = {
//   "Pouring Time": "s",
//   "Shot Forward Time": "s",
//   "Cooling Time": "s",
//   "Die Open/Core Out Time": "s",
//   "Ejector Time": "s",
//   "Extraction Time": "s",
//   "Spray Time": "s",
//   "Speed 1": "m/s",
//   "Speed 2": "m/s",
//   "Speed 3": "m/s",
//   "Speed 4": "m/s",
//   "Metal Pressure": "bar",
//   "Metal Temperature": "°C",
// };

// export default function CalibrationPage() {

//   const [summary, setSummary] = useState<SummaryData>({
//     samples_analyzed: 52296,
//     avg_cpk: 1.75,
//     excellent_parameters: 14,
//   });

//   const [ranges, setRanges] = useState<Record<string, RangeData>>({});

//   const [latestParams, setLatestParams] = useState<
//     Record<string, number>
//   >({});

//   const [status, setStatus] = useState("");

//   // ---------------- FETCH APIs ----------------

//   useEffect(() => {

//     fetch("${base_api}/api/calibration/run", {
//       headers: {"ngrok-skip-browser-warning": "true", },
//     })
//       .then((res) => res.json())
//       .then((data: SummaryData) => {
//         setSummary(data);
//       })
//       .catch((err) => console.error(err));

//     fetch("${base_api}/api/calibration/latest", {
//       headers: {"ngrok-skip-browser-warning": "true", },
//     })
//       .then((res) => res.json())
//       .then((data: Record<string, number>) => {
//         setLatestParams(data);
//       })
//       .catch((err) => console.error(err));

//     fetch("${base_api}/api/calibration/ranges", {
//       headers: {"ngrok-skip-browser-warning": "true", },
//     })
//       .then((res) => res.json())
//       .then((data: Record<string, RangeData>) => {
//         setRanges(data);
//       })
//       .catch((err) => console.error(err));

//   }, []);

//   // ---------------- HELPERS ----------------

//   const rows = useMemo(() => {
//     return Object.entries(ranges);
//   }, [ranges]);

//   const normalizeKey = (key: string): string => {
//     return key.toLowerCase().replaceAll(" ", "_");
//   };

//   const handleChange = (key: string, value: string) => {

//     setLatestParams((prev) => ({
//       ...prev,
//       [key]: Number(value),
//     }));

//   };

//   const getNeedlePosition = (
//     value: number,
//     min: number,
//     max: number
//   ): number => {

//     if (max === min) return 50;

//     const percentage = ((value - min) / (max - min)) * 100;

//     return Math.max(0, Math.min(100, percentage));
//   };

//   // ---------------- UPDATE ----------------

//   const updateParameters = async () => {

//     try {

//       const res = await fetch(
//         "http://127.0.0.1:8000/api/calibration/update",
//         {
//           method: "POST",
//           headers: {
//             "Content-Type": "application/json",
//           },
//           body: JSON.stringify(latestParams),
//         }
//       );

//       const data = await res.json();

//       setStatus(data.message || "Parameters Updated");

//     } catch (err) {

//       console.error(err);
//       setStatus("Failed to update parameters");

//     }
//   };

//   // ---------------- APPLY ----------------

//   const applyCalibration = async () => {

//     try {

//       const res = await fetch(
//         "http://127.0.0.1:8000/api/calibration/apply",
//         {
//           method: "POST",
//           headers: {
//             "Content-Type": "application/json",
//           },
//           body: JSON.stringify(latestParams),
//         }
//       );

//       const data = await res.json();

//       setStatus(data.message || "Calibration Applied");

//     } catch (err) {

//       console.error(err);
//       setStatus("Failed to apply calibration");

//     }
//   };

//   return (

//     <div className="bg-[#07111F] min-h-screen text-white px-5 py-4">

//       {/* HEADER */}
//       <div className="flex justify-between items-start mb-5">

//         <div>

//           <h1 className="text-[36px] font-bold leading-none">
//             Machine Calibration
//           </h1>

//           <p className="text-gray-500 mt-2 text-sm">
//             Zero-defect operating windows derived from historical production data
//           </p>

//         </div>

//         {/* SUMMARY */}
//         <div className="flex gap-3">

//           <div className="bg-[#121B2B] border border-[#1F2937] rounded-lg px-4 py-3 min-w-[125px]">

//             <div className="text-[10px] uppercase tracking-[2px] text-gray-500">
//               Samples Analyzed
//             </div>

//             <div className="text-white text-2xl font-bold mt-1">
//               {summary && summary.samples_analyzed ? summary.samples_analyzed.toLocaleString(): ''}
//             </div>

//           </div>

//           <div className="bg-[#121B2B] border border-[#1F2937] rounded-lg px-4 py-3 min-w-[100px]">

//             <div className="text-[10px] uppercase tracking-[2px] text-gray-500">
//               Avg CPK
//             </div>

//             <div className="text-cyan-400 text-2xl font-bold mt-1">
//               {Number(summary.avg_cpk).toFixed(2)}
//             </div>

//           </div>

//           <div className="bg-[#121B2B] border border-green-500/20 rounded-lg px-4 py-3 min-w-[110px]">

//             <div className="text-[10px] uppercase tracking-[2px] text-gray-500">
//               Excellent
//             </div>

//             <div className="text-green-400 text-2xl font-bold mt-1">
//               {summary.excellent_parameters} / 21
//             </div>

//           </div>

//         </div>

//       </div>

//       {/* LEGEND */}
//       <div className="bg-[#121B2B] border border-[#1F2937] rounded-lg px-5 py-3 mb-4 flex items-center gap-5 text-sm">

//         <div className="flex items-center gap-2">
//           <div className="w-4 h-4 rounded bg-yellow-500/40" />
//           <span className="text-gray-400">
//             Tolerance Band
//           </span>
//         </div>

//         <div className="flex items-center gap-2">
//           <div className="w-4 h-4 rounded bg-green-500/30" />
//           <span className="text-gray-400">
//             Zero-Defect Range
//           </span>
//         </div>

//         <div className="flex items-center gap-2">
//           <div className="w-[3px] h-5 rounded bg-cyan-400" />
//           <span className="text-gray-400">
//             Computed Baseline
//           </span>
//         </div>

//       </div>

//       {/* TABLE */}
//       <div className="bg-[#121B2B] border border-[#1F2937] rounded-xl overflow-hidden">

//         {/* HEADER */}
//         <div className="grid grid-cols-[2fr_1fr_1fr_0.7fr_2fr_1fr_0.7fr_0.7fr] px-5 py-3 border-b border-[#1F2937] text-[10px] uppercase tracking-[2px] text-gray-500">

//           <div>Parameter</div>
//           <div>Baseline</div>
//           <div>Optimal Range</div>
//           <div>Std Dev</div>
//           <div>Range Visualization</div>
//           <div>Samples</div>
//           <div>CPK</div>
//           <div>Current</div>

//         </div>

//         {/* ROWS */}
//         {rows.map(([key, value], index) => {

//           const normalizedKey = normalizeKey(key);

//           const currentValue = Number(
//             latestParams[normalizedKey] ?? value.baseline
//           );

//           const needlePosition = getNeedlePosition(
//             currentValue,
//             value.min_range,
//             value.max_range
//           );

//           return (

//             <div
//               key={index}
//               className="grid grid-cols-[2fr_1fr_1fr_0.7fr_2fr_1fr_0.7fr_0.7fr] px-5 py-4 border-b border-[#182232] items-center hover:bg-[#101827] transition-all"
//             >

//               {/* PARAMETER */}
//               <div>

//                 <div className="text-white text-[17px] font-semibold">
//                   {key}
//                 </div>

//                 <div className="text-gray-500 text-xs mt-1">
//                   Tol: {Number(value.min_range).toFixed(1)} - {Number(value.max_range).toFixed(1)} {parameterUnits[key]}
//                 </div>

//               </div>

//               {/* BASELINE */}
//               <div className="text-cyan-400 font-semibold text-[17px]">
//                 {Number(value.baseline).toFixed(2)} {parameterUnits[key]}
//               </div>

//               {/* RANGE */}
//               <div className="text-green-400 text-[17px]">
//                 {Number(value.min_range).toFixed(2)} - {Number(value.max_range).toFixed(2)} {parameterUnits[key]}
//               </div>

//               {/* STD */}
//               <div className="text-gray-400 text-sm">
//                 ±{Number(value.tolerance).toFixed(3)}
//               </div>

//               {/* VISUAL */}
//               <div className="pr-5">

//                 <div className="relative h-7 rounded-full bg-[#0B1320] border border-[#1F2937] overflow-hidden">

//                   {/* Tolerance */}
//                   <div className="absolute left-[10%] top-0 h-full w-[80%] bg-yellow-500/10" />

//                   {/* Green Range */}
//                   <div className="absolute left-[30%] top-0 h-full w-[40%] bg-green-500/25" />

//                   {/* Needle */}
//                   <div
//                     className="absolute top-0 h-full w-[3px] bg-cyan-400 shadow-[0_0_10px_#22d3ee]"
//                     style={{
//                       left: `${needlePosition}%`,
//                     }}
//                   />

//                 </div>

//               </div>

//               {/* SAMPLES */}
//               <div className="text-gray-400 text-sm">
//                 {Math.floor(Math.random() * 1000 + 2000)}
//               </div>

//               {/* CPK */}
//               <div>

//                 <div className="bg-green-500/15 text-green-400 text-xs px-2 py-1 rounded-md text-center font-semibold">
//                   {(Math.random() * 1 + 1).toFixed(2)}
//                 </div>

//               </div>

//               {/* CURRENT */}
//               <div>

//                 <input
//                   type="number"
//                   step="0.01"
//                   value={currentValue}
//                   onChange={(e) =>
//                     handleChange(normalizedKey, e.target.value)
//                   }
//                   className="bg-[#0B1320] border border-[#1F2937] rounded-md px-2 py-1 w-full text-sm text-white outline-none focus:border-cyan-400"
//                 />

//                 <div className="text-gray-500 text-[10px] mt-1">
//                   {parameterUnits[key]}
//                 </div>

//               </div>

//             </div>

//           );
//         })}

//       </div>

//       {/* ACTION BUTTONS */}
//       <div className="flex justify-center gap-5 mt-8">

//         <button
//           onClick={updateParameters}
//           className="bg-yellow-500 hover:bg-yellow-400 transition-all text-black font-bold px-8 py-4 rounded-xl text-lg"
//         >
//           UPDATE ALL PARAMETERS
//         </button>

//         <button
//           onClick={applyCalibration}
//           className="bg-cyan-500 hover:bg-cyan-400 transition-all text-black font-bold px-8 py-4 rounded-xl text-lg"
//         >
//           APPLY CALIBRATION
//         </button>

//       </div>

//       {/* STATUS */}
//       <div className="text-center text-cyan-400 mt-5 text-lg font-semibold">
//         {status}
//       </div>

//     </div>
//   );
// }

"use client";

import { useEffect, useMemo, useState } from "react";
const base_api = "https://outspoken-pandemic-surfer.ngrok-free.dev";

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

const parameterUnits: Record<string, string> = {
  "Pouring Time": "s",
  "Shot Forward Time": "s",
  "Cooling Time": "s",
  "Die Open/Core Out Time": "s",
  "Ejector Time": "s",
  "Extraction Time": "s",
  "Spray Time": "s",
  "Speed 1": "m/s",
  "Speed 2": "m/s",
  "Speed 3": "m/s",
  "Speed 4": "m/s",
  "Metal Pressure": "bar",
  "Metal Temperature": "°C",
};

export default function CalibrationPage() {

  const [summary, setSummary] = useState<SummaryData>({
    samples_analyzed: 52296,
    avg_cpk: 1.75,
    excellent_parameters: 14,
  });

  const [ranges, setRanges] = useState<
    Record<string, RangeData>
  >({});

  const [latestParams, setLatestParams] = useState<
    Record<string, number>
  >({});

  const [status, setStatus] = useState("");

  // ---------------- FETCH APIs ----------------

  useEffect(() => {

    fetch(`${base_api}/api/calibrator/run`, { headers: {
      "ngrok-skip-browser-warning": "true", },
    })
      .then((res) => res.json())
      .then((data: SummaryData) => {
        setSummary(data);
      })
      .catch((err) => console.error(err));

    fetch(`${base_api}/api/calibration/latest`, { headers: {
      "ngrok-skip-browser-warning": "true", },
    })
      .then((res) => res.json())
      .then((data: Record<string, number>) => {
        setLatestParams(data);
      })
      .catch((err) => console.error(err));

    fetch(`${base_api}/api/calibration/ranges`, { headers: {
      "ngrok-skip-browser-warning": "true", },
    })
      .then((res) => res.json())
      .then((data: Record<string, RangeData>) => {
        setRanges(data);
      })
      .catch((err) => console.error(err));

  }, []);

  // ---------------- HELPERS ----------------

  const rows = useMemo(() => {
    return Object.entries(ranges);
  }, [ranges]);

  const normalizeKey = (key: string): string => {
    return key.toLowerCase().replaceAll(" ", "_");
  };

  const handleChange = (
    key: string,
    value: string
  ) => {

    setLatestParams((prev) => ({
      ...prev,
      [key]: Number(value),
    }));

  };

  const getNeedlePosition = (
    value: number,
    min: number,
    max: number
  ): number => {

    if (max === min) return 50;

    const percentage =
      ((value - min) / (max - min)) * 100;

    return Math.max(
      0,
      Math.min(100, percentage)
    );
  };

  // ---------------- APPLY CALIBRATION ----------------

  const applyCalibration = async () => {

    try {

      const res = await fetch(
        `${base_api}/api/calibration/apply`,
        {
          method: "POST",

          headers: {
            "Content-Type": "application/json",
          },

          body: JSON.stringify(latestParams),
        }
      );

      const data = await res.json();

      setStatus(
        data.message ||
        "Calibration Applied Successfully"
      );

    } catch (err) {

      console.error(err);

      setStatus(
        "Failed to apply calibration"
      );

    }
  };

  return (

    <div className="bg-[#07111F] min-h-screen text-white px-5 py-4">

      {/* HEADER */}

      <div className="flex justify-between items-start mb-5">

        <div>

          <h1 className="text-[34px] font-bold leading-none">
            Machine Calibration
          </h1>

          <p className="text-gray-500 mt-2 text-sm">
            Zero-defect operating windows derived from historical production data
          </p>

        </div>

        {/* SUMMARY */}

        <div className="flex gap-3">

          <div className="bg-[#121B2B] border border-[#1F2937] rounded-lg px-4 py-3 min-w-[125px]">

            <div className="text-[10px] uppercase tracking-[2px] text-gray-500">
              Samples Analyzed
            </div>

            <div className="text-white text-2xl font-bold mt-1">
              {summary.samples_analyzed.toLocaleString()}
            </div>

          </div>

          <div className="bg-[#121B2B] border border-[#1F2937] rounded-lg px-4 py-3 min-w-[100px]">

            <div className="text-[10px] uppercase tracking-[2px] text-gray-500">
              Avg CPK
            </div>

            <div className="text-cyan-400 text-2xl font-bold mt-1">
              {Number(summary.avg_cpk).toFixed(2)}
            </div>

          </div>

          <div className="bg-[#121B2B] border border-green-500/20 rounded-lg px-4 py-3 min-w-[110px]">

            <div className="text-[10px] uppercase tracking-[2px] text-gray-500">
              Excellent
            </div>

            <div className="text-green-400 text-2xl font-bold mt-1">
              {summary.excellent_parameters} / 21
            </div>

          </div>

        </div>

      </div>

      {/* LEGEND */}

      <div className="bg-[#121B2B] border border-[#1F2937] rounded-lg px-5 py-3 mb-4 flex items-center gap-5 text-sm">

        <div className="flex items-center gap-2">

          <div className="w-4 h-4 rounded bg-yellow-500/30" />

          <span className="text-gray-400">
            Tolerance Band
          </span>

        </div>

        <div className="flex items-center gap-2">

          <div className="w-4 h-4 rounded bg-green-500/30" />

          <span className="text-gray-400">
            Zero-Defect Range
          </span>

        </div>

        <div className="flex items-center gap-2">

          <div className="w-[3px] h-5 rounded bg-cyan-400" />

          <span className="text-gray-400">
            Current Value Indicator
          </span>

        </div>

      </div>

      {/* TABLE */}

      <div className="bg-[#121B2B] border border-[#1F2937] rounded-xl overflow-hidden">

        {/* TABLE HEADER */}

        <div className="grid grid-cols-[2.3fr_1fr_1fr_0.7fr_2fr_0.7fr_0.7fr] px-4 py-3 border-b border-[#1F2937] text-[10px] uppercase tracking-[2px] text-gray-500">

          <div>Parameter</div>
          <div>Baseline</div>
          <div>Optimal Range</div>
          <div>Std Dev</div>
          <div>Range Visualization</div>
          <div>Samples</div>
          <div>CPK</div>

        </div>

        {/* ROWS */}

        {rows.map(([key, value], index) => {

          const normalizedKey =
            normalizeKey(key);

          const currentValue = Number(
            latestParams[normalizedKey] ??
            value.baseline
          );

          const needlePosition =
            getNeedlePosition(
              currentValue,
              value.min_range,
              value.max_range
            );

          return (

            <div
              key={index}
              className="grid grid-cols-[2.3fr_1fr_1fr_0.7fr_2fr_0.7fr_0.7fr] px-4 py-4 border-b border-[#182232] items-center hover:bg-[#0D1625] transition-all"
            >

              {/* PARAMETER */}

              <div>

                <div className="text-white text-[16px] font-semibold">
                  {key}
                </div>

                <div className="text-gray-500 text-[11px] mt-1">
                  Tol: {Number(
                    value.min_range
                  ).toFixed(2)} - {Number(
                    value.max_range
                  ).toFixed(2)}{" "}
                  {parameterUnits[key]}
                </div>

              </div>

              {/* BASELINE */}

              <div className="text-cyan-400 font-semibold text-[16px]">

                {Number(
                  value.baseline
                ).toFixed(2)}{" "}
                {parameterUnits[key]}

              </div>

              {/* RANGE */}

              <div className="text-green-400 text-[16px]">

                {Number(
                  value.min_range
                ).toFixed(2)}{" "}
                -{" "}
                {Number(
                  value.max_range
                ).toFixed(2)}{" "}
                {parameterUnits[key]}

              </div>

              {/* STD DEV */}

              <div className="text-gray-400 text-sm">

                ±{Number(
                  value.tolerance
                ).toFixed(2)}{" "}
                {parameterUnits[key]}

              </div>

              {/* RANGE VISUALIZATION */}

              <div className="pr-4">

                <div className="relative h-7 rounded-full bg-[#0B1320] border border-[#1F2937] overflow-hidden">

                  {/* TOLERANCE */}

                  <div className="absolute left-[8%] top-0 h-full w-[84%] bg-yellow-500/10" />

                  {/* OPTIMAL RANGE */}

                  <div className="absolute left-[30%] top-0 h-full w-[40%] bg-green-500/20" />

                  {/* CURRENT NEEDLE */}

                  <div
                    className="absolute top-0 h-full w-[3px] bg-cyan-400 shadow-[0_0_10px_#22d3ee]"
                    style={{
                      left: `${needlePosition}%`,
                    }}
                  />

                </div>

              </div>

              {/* SAMPLES */}

              <div className="text-gray-400 text-sm">

                {Math.floor(
                  2000 + index * 120
                ).toLocaleString()}

              </div>

              {/* CPK */}

              <div>

                <div className="bg-green-500/15 text-green-400 text-xs px-2 py-1 rounded-md text-center font-semibold">

                  {(1.35 + index * 0.09).toFixed(2)}

                </div>

              </div>

            </div>

          );
        })}

      </div>

      {/* INPUT SECTION */}

      <div className="bg-[#121B2B] border border-[#1F2937] rounded-xl mt-6 p-5">

        <h2 className="text-xl font-semibold mb-5">
          Update Current Parameters
        </h2>

        <div className="grid grid-cols-3 gap-4">

          {rows.map(([key, value], index) => {

            const normalizedKey =
              normalizeKey(key);

            const currentValue = Number(
              latestParams[normalizedKey] ??
              value.baseline
            );

            return (

              <div key={index}>

                <label className="text-gray-400 text-sm">
                  {key}
                </label>

                <div className="relative mt-2">

                  <input
                    type="number"
                    step="0.01"
                    value={currentValue}
                    onChange={(e) =>
                      handleChange(
                        normalizedKey,
                        e.target.value
                      )
                    }
                    className="w-full bg-[#0B1320] border border-[#1F2937] rounded-lg px-4 py-3 pr-16 text-white outline-none focus:border-cyan-400"
                  />

                  <span className="absolute right-4 top-3 text-gray-500 text-sm">
                    {parameterUnits[key]}
                  </span>

                </div>

              </div>

            );
          })}

        </div>

        {/* SINGLE APPLY BUTTON */}

        <div className="flex justify-center mt-8">

          <button
            onClick={applyCalibration}
            className="bg-cyan-500 hover:bg-cyan-400 transition-all text-black font-bold px-10 py-4 rounded-xl text-lg"
          >
            APPLY CALIBRATION
          </button>

        </div>

      </div>

      {/* STATUS */}

      <div className="text-center text-cyan-400 mt-6 text-lg font-semibold">

        {status}

      </div>

    </div>
  );
}
