// Health data for the Health section.
//
// Right now this returns realistic *sample* data so the dashboard works without any OAuth changes.
// To use REAL Google Fit data later: replace the body of fetchHealthSummary with a call to a
// backend endpoint (e.g. GET /api/health) that reads the Google Fit REST API using fitness.*.read
// scopes (steps: com.google.step_count.delta, heart rate: com.google.heart_rate.bpm, blood
// pressure: com.google.blood_pressure, etc.) and returns the same shape as below.

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

// Small deterministic PRNG so a given person's charts stay stable across reloads.
function seededRand(str) {
  let h = 2166136261;
  const s = str || 'seed';
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return () => {
    h += 0x6d2b79f5; let t = h;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export async function fetchHealthSummary(userId, profileId) {
  const rnd = seededRand(`${userId || ''}|${profileId || 'self'}`);
  const ri = (a, b) => Math.floor(a + rnd() * (b - a + 1));
  const rf = (a, b, d = 1) => +(a + rnd() * (b - a)).toFixed(d);

  const steps    = DAYS.map((day) => ({ day, value: ri(3800, 12500) }));
  const heartRate = DAYS.map((day) => ({ day, value: ri(61, 88) }));
  const bp       = DAYS.map((day) => ({ day, sys: ri(112, 136), dia: ri(72, 89) }));
  const sleep    = DAYS.map((day) => ({ day, value: rf(5.8, 8.4) }));
  const calories = DAYS.map((day) => ({ day, value: ri(240, 680) }));

  const last = (a) => a[a.length - 1];
  const avg = (a, k = 'value') => Math.round(a.reduce((s, x) => s + x[k], 0) / a.length);

  return {
    source: 'Google Fit',
    sample: true,
    today: {
      steps: last(steps).value, stepsGoal: 10000,
      hr: last(heartRate).value, hrAvg: avg(heartRate),
      bpSys: last(bp).sys, bpDia: last(bp).dia,
      sleep: last(sleep).value,
      calories: last(calories).value, caloriesGoal: 500,
    },
    steps, heartRate, bp, sleep, calories,
  };
}
