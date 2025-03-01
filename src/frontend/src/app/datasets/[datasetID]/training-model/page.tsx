'use client';
import { useParams } from 'next/navigation';
import React from 'react';

const TrainingModel = () => {
  const params = useParams();
  console.log(params);
  
  return (
    <div>Training page for dataset ID: {params?.datasetID}</div>
  );
}

export default TrainingModel;