import React from 'react';

interface Props {
  params: {
    datasetID: string;
  };
}

const Page = ({ params }: Props) => {
  return (
    <div>
      Huấn luyện dataset với ID: <b>{params.datasetID}</b>
    </div>
  );
};

export default Page;
