-- phpMyAdmin SQL Dump
-- version 4.1.14
-- http://www.phpmyadmin.net
--
-- Host: 127.0.0.1
-- Generation Time: Mar 01, 2022 at 11:14 PM
-- Server version: 5.6.17
-- PHP Version: 5.5.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;

--
-- Database: `ema`
--

-- --------------------------------------------------------

--
-- Table structure for table `recomm_saved_memory`
--

CREATE TABLE IF NOT EXISTS `recomm_saved_memory` (
  `FirstStartDate` varchar(500) NOT NULL,
  `deploymentID` varchar(500) NOT NULL DEFAULT 'NA',
  `baselineTimeLeft` varchar(500) NOT NULL DEFAULT 'NA',
  `lastUpdated` varchar(500) NOT NULL DEFAULT 'NA',
  `morningStartTime` varchar(500) NOT NULL DEFAULT 'NA',
  `eveningEndTime` varchar(500) NOT NULL DEFAULT 'NA',
  `maxMessages` int(255) NOT NULL DEFAULT '4',
  PRIMARY KEY (`deploymentID`),
  UNIQUE KEY `empathid_UNIQUE` (`deploymentID`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

--
-- Dumping data for table `recomm_saved_memory`
--

INSERT INTO `recomm_saved_memory` (`FirstStartDate`, `deploymentID`, `baselineTimeLeft`, `lastUpdated`, `morningStartTime`, `eveningEndTime`, `maxMessages`) VALUES
('2021-08-02 16:54:40', '08022021', '0', '2022-03-01 11:44:35', '8:01:00', '22:30:00', 4);

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
