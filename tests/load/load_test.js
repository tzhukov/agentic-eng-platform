import http from 'k6/http';
import { check, sleep } from 'k6';

// This script simulates load on the /query endpoint.
// It can be run with different RPS targets using k6 flags or by adjusting stages.

export let options = {
  stages: [
    { duration: '2m', target: __ENV.TARGET_VUS || 5 }, // Ramp up
    { duration: '5m', target: __ENV.TARGET_VUS || 5 }, // Stay at target
    { duration: '2m', target: 0 },                    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<30000'], // 95% of requests must be below 30s (SLO)
    http_req_failed: ['rate<0.005'],    // less than 0.5% errors (SLO)
  },
};

export default function () {
  const url = __ENV.API_URL || 'http://localhost:8000/query';
  const payload = JSON.stringify({
    query: 'Write a simple python function to greet the world.',
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
    timeout: '60s', // Allow for long-running agent tasks
  };

  let res = http.post(url, payload, params);
  
  check(res, {
    'is status 200': (r) => r.status === 200,
  });

  sleep(1);
}
