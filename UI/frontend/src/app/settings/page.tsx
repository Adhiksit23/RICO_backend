
"use client";

import { useState } from "react";

export default function SettingsPage() {

  const [status, setStatus] = useState("");

  const [customer, setCustomer] = useState("");
  const [part, setPart] = useState("");
  const [machine, setMachine] = useState("");
  const [die, setDie] = useState("");

  const handleIoTStart = () => {
    setStatus("IoT Data Fetching Started...");
  };

  const handleIoTStop = () => {
    setStatus("IoT Data Fetching Stopped");
  };

  const handleTrain = async () => {

    try {

      const res = await fetch(
        "http://127.0.0.1:8000/api/trainer/train"
      );

      const data = await res.json();

      setStatus(data.status);

    } catch (err) {

      console.error(err);

    }
  };

  const handleCalibration = async () => {

    try {

      await fetch(
        "http://127.0.0.1:8000/api/calibrator/run"
      );

      setStatus("Calibration Triggered");

    } catch (err) {

      console.error(err);

    }
  };

  return (

    <div className="bg-[#081122] min-h-screen text-white px-6 py-5">

      {/* HEADER */}
      <div className="mb-8">

        <h1 className="text-[42px] font-bold text-cyan-400 leading-none">
          INDUSTRY SETTINGS & CONTROL
        </h1>

        <p className="text-gray-500 mt-2">
          Enterprise-level configuration for customers, machines, dies, IoT and AI workflows
        </p>

      </div>

      {/* TOP GRID */}
      <div className="grid grid-cols-2 gap-6 mb-6">

        {/* CUSTOMER MANAGEMENT */}
        <div className="bg-[#151C2C] border border-[#252D3D] rounded-2xl p-6">

          <div className="flex justify-between items-start mb-6">

            <div>

              <h2 className="text-2xl font-semibold">
                Customer Management
              </h2>

              <p className="text-gray-500 mt-2">
                Create and manage industrial customers
              </p>

            </div>

            <div className="text-5xl">
              🏭
            </div>

          </div>

          <div className="space-y-4">

            <div>

              <label className="text-gray-400 text-sm">
                Customer Name
              </label>

              <input
                type="text"
                value={customer}
                onChange={(e) => setCustomer(e.target.value)}
                placeholder="Enter Customer Name"
                className="w-full mt-2 bg-[#0F172A] border border-[#252D3D] rounded-xl px-4 py-3 outline-none"
              />

            </div>

            <button
              className="w-full bg-cyan-500 hover:bg-cyan-400 transition-all text-black font-bold py-4 rounded-xl"
            >
              CREATE CUSTOMER
            </button>

          </div>

        </div>

        {/* PART MASTER */}
        <div className="bg-[#151C2C] border border-[#252D3D] rounded-2xl p-6">

          <div className="flex justify-between items-start mb-6">

            <div>

              <h2 className="text-2xl font-semibold">
                Part Master
              </h2>

              <p className="text-gray-500 mt-2">
                Add industrial parts under customers
              </p>

            </div>

            <div className="text-5xl">
              🧩
            </div>

          </div>

          <div className="space-y-4">

            <div>

              <label className="text-gray-400 text-sm">
                Part Name
              </label>

              <input
                type="text"
                value={part}
                onChange={(e) => setPart(e.target.value)}
                placeholder="Enter Part Name"
                className="w-full mt-2 bg-[#0F172A] border border-[#252D3D] rounded-xl px-4 py-3 outline-none"
              />

            </div>

            <div>

              <label className="text-gray-400 text-sm">
                Select Customer
              </label>

              <select className="w-full mt-2 bg-[#0F172A] border border-[#252D3D] rounded-xl px-4 py-3 outline-none">

                <option>Tata</option>
                <option>Mahindra</option>
                <option>Hyundai</option>

              </select>

            </div>

            <button
              className="w-full bg-green-500 hover:bg-green-400 transition-all text-black font-bold py-4 rounded-xl"
            >
              CREATE PART
            </button>

          </div>

        </div>

      </div>

      {/* SECOND GRID */}
      <div className="grid grid-cols-2 gap-6 mb-6">

        {/* MACHINE MASTER */}
        <div className="bg-[#151C2C] border border-[#252D3D] rounded-2xl p-6">

          <div className="flex justify-between items-start mb-6">

            <div>

              <h2 className="text-2xl font-semibold">
                Machine Master
              </h2>

              <p className="text-gray-500 mt-2">
                Configure machines and IoT connectivity
              </p>

            </div>

            <div className="text-5xl">
              ⚙️
            </div>

          </div>

          <div className="space-y-4">

            <input
              type="text"
              value={machine}
              onChange={(e) => setMachine(e.target.value)}
              placeholder="Machine ID"
              className="w-full bg-[#0F172A] border border-[#252D3D] rounded-xl px-4 py-3 outline-none"
            />

            <select className="w-full bg-[#0F172A] border border-[#252D3D] rounded-xl px-4 py-3 outline-none">

              <option>HPDC</option>
              <option>LPDC</option>
              <option>Gravity Die Casting</option>

            </select>

            <input
              type="text"
              placeholder="Factory Location"
              className="w-full bg-[#0F172A] border border-[#252D3D] rounded-xl px-4 py-3 outline-none"
            />

            <button
              className="w-full bg-yellow-500 hover:bg-yellow-400 transition-all text-black font-bold py-4 rounded-xl"
            >
              ADD MACHINE
            </button>

          </div>

        </div>

        {/* DIE MASTER */}
        <div className="bg-[#151C2C] border border-[#252D3D] rounded-2xl p-6">

          <div className="flex justify-between items-start mb-6">

            <div>

              <h2 className="text-2xl font-semibold">
                Die Master
              </h2>

              <p className="text-gray-500 mt-2">
                Manage die lifecycle and compatibility
              </p>

            </div>

            <div className="text-5xl">
              🏗️
            </div>

          </div>

          <div className="space-y-4">

            <input
              type="text"
              value={die}
              onChange={(e) => setDie(e.target.value)}
              placeholder="Die ID"
              className="w-full bg-[#0F172A] border border-[#252D3D] rounded-xl px-4 py-3 outline-none"
            />

            <select className="w-full bg-[#0F172A] border border-[#252D3D] rounded-xl px-4 py-3 outline-none">

              <option>Gear Housing</option>
              <option>Engine Block</option>

            </select>

            <select className="w-full bg-[#0F172A] border border-[#252D3D] rounded-xl px-4 py-3 outline-none">

              <option>850T-1</option>
              <option>850T-2</option>

            </select>

            <button
              className="w-full bg-pink-500 hover:bg-pink-400 transition-all text-black font-bold py-4 rounded-xl"
            >
              CREATE DIE
            </button>

          </div>

        </div>

      </div>

      {/* IoT CONTROL */}
      <div className="bg-[#151C2C] border border-[#252D3D] rounded-2xl p-6 mb-6">

        <div className="flex justify-between items-start mb-6">

          <div>

            <h2 className="text-2xl font-semibold">
              IoT Data Control
            </h2>

            <p className="text-gray-500 mt-2">
              Start live machine and die parameter fetching
            </p>

          </div>

          <div className="text-5xl">
            📡
          </div>

        </div>

        <div className="grid grid-cols-3 gap-5 mb-6">

          <div className="bg-[#0F172A] border border-[#252D3D] rounded-xl p-5">

            <div className="text-gray-500 text-sm">
              Connected Machines
            </div>

            <div className="text-4xl font-bold text-cyan-400 mt-3">
              12
            </div>

          </div>

          <div className="bg-[#0F172A] border border-[#252D3D] rounded-xl p-5">

            <div className="text-gray-500 text-sm">
              Active IoT Streams
            </div>

            <div className="text-4xl font-bold text-green-400 mt-3">
              8
            </div>

          </div>

          <div className="bg-[#0F172A] border border-[#252D3D] rounded-xl p-5">

            <div className="text-gray-500 text-sm">
              Last Sync
            </div>

            <div className="text-xl font-bold text-yellow-400 mt-4">
              2 mins ago
            </div>

          </div>

        </div>

        <div className="flex gap-5">

          <button
            onClick={handleIoTStart}
            className="bg-cyan-500 hover:bg-cyan-400 transition-all text-black font-bold px-8 py-4 rounded-xl"
          >
            START FETCHING IoT
          </button>

          <button
            onClick={handleIoTStop}
            className="bg-red-500 hover:bg-red-400 transition-all text-white font-bold px-8 py-4 rounded-xl"
          >
            STOP IoT
          </button>

        </div>

      </div>

      {/* AI CONTROLS */}
      <div className="grid grid-cols-2 gap-6">

        {/* MODEL TRAINING */}
        <div className="bg-[#151C2C] border border-[#252D3D] rounded-2xl p-6">

          <h2 className="text-2xl font-semibold mb-4">
            AI Model Training
          </h2>

          <p className="text-gray-500 mb-5">
            Train defect prediction models using industrial datasets
          </p>

          <button
            onClick={handleTrain}
            className="w-full bg-cyan-500 hover:bg-cyan-400 transition-all text-black font-bold py-4 rounded-xl"
          >
            TRAIN MODEL
          </button>

        </div>

        {/* CALIBRATION */}
        <div className="bg-[#151C2C] border border-[#252D3D] rounded-2xl p-6">

          <h2 className="text-2xl font-semibold mb-4">
            Machine Calibration
          </h2>

          <p className="text-gray-500 mb-5">
            Run AI-assisted calibration workflow
          </p>

          <button
            onClick={handleCalibration}
            className="w-full bg-green-500 hover:bg-green-400 transition-all text-black font-bold py-4 rounded-xl"
          >
            RUN CALIBRATION
          </button>

        </div>

      </div>

      {/* STATUS */}
      <div className="text-cyan-400 text-lg font-semibold mt-8">
        {status}
      </div>

    </div>
  );
}

