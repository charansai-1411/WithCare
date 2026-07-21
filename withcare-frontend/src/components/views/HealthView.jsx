import React, { useEffect, useState, useCallback } from 'react';
import { fetchHealthSummary } from '../../services/healthApi';
import { BarChart, LineChart, Ring } from '../ui/Charts';
import { SkeletonList } from '../ui/Skeleton';
import VitalsPanel from '../VitalsPanel';

function Sym({ name, className = '', fill = false, style }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`} style={style}>{name}</span>;
}

function ChartCard({ icon, title, sub, color, children }) {
  return (
    <section className="bg-surface-container-lowest rounded-card border border-outline-variant p-5 elev-1">
      <div className="flex items-center gap-2.5 mb-3">
        <span className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: color + '1F' }}>
          <Sym name={icon} className="text-[18px]" fill style={{ color }} />
        </span>
        <div className="min-w-0">
          <h3 className="font-title-lg text-[15px] text-on-surface leading-tight">{title}</h3>
          {sub && <div className="text-[12px] text-on-surface-variant">{sub}</div>}
        </div>
      </div>
      {children}
    </section>
  );
}

function StatCard({ icon, color, label, value, unit, foot }) {
  return (
    <div className="bg-surface-container-lowest rounded-card border border-outline-variant p-4 elev-1 flex flex-col gap-1">
      <div className="flex items-center gap-2 text-[12px] font-medium text-on-surface-variant">
        <Sym name={icon} className="text-[17px]" fill style={{ color }} />{label}
      </div>
      <div className="flex items-baseline gap-1">
        <span className="text-[24px] font-bold text-on-surface leading-none">{value}</span>
        {unit && <span className="text-[12px] text-on-surface-variant">{unit}</span>}
      </div>
      {foot && <div className="text-[11.5px] text-on-surface-variant">{foot}</div>}
    </div>
  );
}

const G = { blue: '#1a73e8', green: '#34a853', red: '#ea4335', yellow: '#f9ab00', purple: '#a142f4' };

export default function HealthView({ userId, profile }) {
  const [data, setData] = useState(null);
  const load = useCallback(() => {
    setData(null);
    fetchHealthSummary(userId, profile?.id).then(setData);
  }, [userId, profile?.id]);
  useEffect(() => { load(); }, [load]);

  const who = profile?.name || 'You';
  const t = data?.today;

  return (
    <div className="flex-1 overflow-y-auto px-8 py-7 bg-background">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-start gap-4 mb-6">
          <div className="flex-1">
            <h1 className="font-headline-lg text-[24px] text-on-surface">Health</h1>
            <p className="text-[14px] text-on-surface-variant mt-0.5 flex items-center gap-2 flex-wrap">
              <span>{who}’s activity this week</span>
              <span className="inline-flex items-center gap-1 text-[11.5px] font-medium text-g-green-text bg-g-green-tint px-2 py-0.5 rounded-full">
                <Sym name="monitoring" className="text-[13px]" /> Synced from Google Fit
              </span>
            </p>
          </div>
          <button onClick={load}
            className="flex items-center gap-1.5 px-4 py-2 rounded-full border border-outline-variant text-on-surface-variant text-[13px] font-medium hover:bg-surface-container shrink-0">
            <Sym name="refresh" className="text-[18px]" /> Refresh
          </button>
        </div>

        {/* Manually-logged vitals + trends (works without any connector) */}
        <VitalsPanel userId={userId} profile={profile} />

        <h2 className="font-title-lg text-[17px] text-on-surface mb-3 flex items-center gap-2">
          <Sym name="monitoring" className="text-primary text-[20px]" fill /> Google Fit activity
        </h2>

        {!data ? <SkeletonList count={3} /> : (
          <>
            {/* Today KPI row */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5 mb-4">
              <div className="bg-surface-container-lowest rounded-card border border-outline-variant p-4 elev-1 flex items-center gap-3">
                <Ring value={t.steps} goal={t.stepsGoal} color={G.blue} size={72} stroke={8}>
                  <Sym name="directions_walk" className="text-[20px]" fill style={{ color: G.blue }} />
                </Ring>
                <div className="min-w-0">
                  <div className="text-[12px] text-on-surface-variant">Steps today</div>
                  <div className="text-[22px] font-bold text-on-surface leading-tight">{t.steps.toLocaleString('en-IN')}</div>
                  <div className="text-[11.5px] text-on-surface-variant">of {t.stepsGoal.toLocaleString('en-IN')}</div>
                </div>
              </div>
              <StatCard icon="favorite" color={G.red} label="Heart rate" value={t.hr} unit="bpm" foot={`avg ${t.hrAvg} bpm`} />
              <StatCard icon="ecg_heart" color={G.purple} label="Blood pressure" value={`${t.bpSys}/${t.bpDia}`} unit="mmHg" foot="last reading" />
              <StatCard icon="bedtime" color={G.blue} label="Sleep" value={t.sleep} unit="hrs" foot="last night" />
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 m3-stagger">
              <ChartCard icon="directions_walk" title="Steps" sub="Daily · goal 10,000" color={G.blue}>
                <BarChart data={data.steps} color={G.blue} unit=" steps" goal={t.stepsGoal} />
              </ChartCard>
              <ChartCard icon="favorite" title="Heart rate" sub="bpm" color={G.red}>
                <LineChart data={data.heartRate} unit=" bpm" series={[{ key: 'value', color: G.red, label: 'HR' }]} />
              </ChartCard>
              <ChartCard icon="ecg_heart" title="Blood pressure" sub="Systolic / Diastolic · mmHg" color={G.purple}>
                <LineChart data={data.bp} unit=" mmHg" series={[
                  { key: 'sys', color: G.purple, label: 'Systolic' },
                  { key: 'dia', color: G.blue, label: 'Diastolic' },
                ]} />
                <div className="flex items-center gap-4 mt-1.5 text-[11.5px] text-on-surface-variant">
                  <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full" style={{ background: G.purple }} />Systolic</span>
                  <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full" style={{ background: G.blue }} />Diastolic</span>
                </div>
              </ChartCard>
              <ChartCard icon="bedtime" title="Sleep" sub="hours per night" color={G.green}>
                <BarChart data={data.sleep} color={G.green} unit=" hrs" />
              </ChartCard>
              <ChartCard icon="local_fire_department" title="Active calories" sub="kcal burned · goal 500" color={G.yellow}>
                <BarChart data={data.calories} color={G.yellow} unit=" kcal" goal={t.caloriesGoal} />
              </ChartCard>
            </div>

            <div className="flex items-start gap-3 mt-6 p-4 rounded-card bg-primary-fixed/40 border border-primary/10">
              <Sym name="info" className="text-primary text-[20px]" fill />
              <p className="text-[12.5px] text-on-surface-variant">
                Showing sample activity data for the demo. Once your backend is authorized with Google Fit
                fitness scopes, these charts fill with your real steps, heart rate and blood pressure.
                WithCare shows your data — it never diagnoses; check readings with your doctor.
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
