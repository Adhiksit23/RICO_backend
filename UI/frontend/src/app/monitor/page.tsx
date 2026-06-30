"use client";

import { useEffect, useState } from "react";

import GaugeCard from "@/components/GaugeCard";
import ParameterGauge from "@/components/ParameterGauge";

export default function MonitorPage() {
  const [predictionData, setPredictionData] = useState({
    non_filling: 0,
    blowhole: 0,
    porosity: 0,
    crack: 0,
    shrinkage: 0,
    chipoff: 0
  });

  // useEffect(() => {
  //   fetch("http://127.0.0.1:8000/api/predictor/predict")
  //     .then((res) => res.json())
  //     .then((data) => {
  //       setPredictionData(data);
  //     })
  //     .catch((err) => {
  //       console.error(err);
  //     });
  // }, []);

  useEffect(() => {
  const fetchPredictionData = () => {
    fetch("http://127.0.0.1:8000/api/predictor/predict")
      .then((res) => res.json())
      .then((data) => {
        setPredictionData(data);
      })
      .catch((err) => {
        console.error(err);
      });
  };

  // Initial fetch
  fetchPredictionData();

  // Refresh every 5 seconds
  const interval = setInterval(fetchPredictionData, 60000);

  return () => clearInterval(interval);
}, []);

  const getPredictionStatus = (value: number) => {
  if (value < 10) {
    return {
      status: "LOW",
      color: "#22C55E", // Green
    };
  }

  if (value <= 50) {
    return {
      status: "MED",
      color: "#F59E0B", // Orange
    };
  }

  return {
    status: "HIGH",
    color: "#EF4444", // Red
  };
};

  // const predictions = [
  //   {
  //     label: "Non-filling",
  //     subtitle: "Incomplete cavity fill",
  //     value: predictionData.non_filling,
  //     status: "HIGH",
  //     color: "#EF4444",
  //   },
  //   {
  //     label: "Blowhole",
  //     subtitle: "Trapped gas cavities",
  //     value: predictionData.blowhole,
  //     status: "LOW",
  //     color: "#22C55E",
  //   },
  //   {
  //     label: "Porosity",
  //     subtitle: "Micro voids in structure",
  //     value: predictionData.porosity,
  //     status: "MED",
  //     color: "#F59E0B",
  //   },
  //   {
  //     label: "Shrinkage",
  //     subtitle: "Volumetric contraction",
  //     value: 23.5,
  //     status: "LOW",
  //     color: "#22C55E",
  //   },
  //   {
  //     label: "Chip-off",
  //     subtitle: "Surface fragment loss",
  //     value: 10.1,
  //     status: "LOW",
  //     color: "#22C55E",
  //   },
  //   {
  //     label: "Crack",
  //     subtitle: "Structural fracture lines",
  //     value: 31.2,
  //     status: "MED",
  //     color: "#F59E0B",
  //   },
  // ];
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
  const parameters = [
    {
      name: "Cooling Time",
      value: "13.7 s",
      tolerance: "13.6 - 14 s",
      status: "OK",
    },
    {
      name: "Spray Time",
      value: "14.5 s",
      tolerance: "14.3 - 15.1 s",
      status: "OK",
    },
    {
      name: "Speed 2",
      value: "0.31 m/s",
      tolerance: "0.3 - 0.32 m/s",
      status: "OK",
    },
    {
      name: "Speed 4",
      value: "3.37 m/s",
      tolerance: "3.35 - 3.39 m/s",
      status: "OK",
    },
    {
      name: "Acc Position",
      value: "226.6 mm",
      tolerance: "264 - 270 mm",
      status: "FAIL",
    },
    {
      name: "Deacc Position",
      value: "701.1 mm",
      tolerance: "696 - 710 mm",
      status: "OK",
    },
    {
      name: "Intensification Time",
      value: "57.9 s",
      tolerance: "53 - 77 s",
      status: "OK",
    },
    {
      name: "Metal Pressure",
      value: "66.4 MPa",
      tolerance: "65 - 67 MPa",
      status: "OK",
    },
    {
      name: "Biscuit Thickness",
      value: "21.6 mm",
      tolerance: "21 - 26 mm",
      status: "OK",
    },
    {
      name: "Clamp Force",
      value: "100.0 %",
      tolerance: "97 - 103 %",
      status: "OK",
    },
    {
      name: "Metal Temperature",
      value: "661.0 °C",
      tolerance: "654 - 663 °C",
      status: "OK",
    },
    {
      name: "Fixed Die Temp F-1",
      value: "205.3 °C",
      tolerance: "180 - 280 °C",
      status: "OK",
    },
  ];

  return (
    <div className="bg-[#0B1120] min-h-screen text-white px-6 py-5">
      {/* Header */}
      <div className="flex justify-between items-start mb-5">
        <div>
          <h1 className="text-[38px] font-bold leading-none">
            Die Casting Process Monitor
          </h1>

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
              15/16 OK
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
          16 key parameters monitored against tolerance limits
        </p>
      </div>

      {/* Parameters Grid */}
      <div className="grid grid-cols-4 gap-4">
        {parameters.map((item) => (
          <ParameterGauge
            key={item.name}
            name={item.name}
            value={item.value}
            tolerance={item.tolerance}
            status={item.status}
          />
        ))}
      </div>

      {/* Footer */}
      <div className="text-center text-gray-500 text-xs mt-5">
        Data refreshes every 5 seconds • Simulated IoT feed
      </div>
    </div>
  );
}
