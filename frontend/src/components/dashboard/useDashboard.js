import { useEffect, useState } from "react";

import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";

export default function useDashboard(endpoint, range) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setData(null);
    setError("");
    if (!range.from || !range.to) {
      setLoading(false);
      return undefined;
    }
    setLoading(true);
    client
      .get(endpoint, { params: { from: range.from, to: range.to } })
      .then(({ data: response }) => {
        if (active) setData(response);
      })
      .catch((requestError) => {
        if (active) setError(errorMessage(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [endpoint, range.from, range.to, revision]);
  return { data, loading, error, refresh: () => setRevision((value) => value + 1) };
}
