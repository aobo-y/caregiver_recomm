-- phpMyAdmin SQL Dump
-- version 4.1.14
-- http://www.phpmyadmin.net
--
-- Host: 127.0.0.1
-- Generation Time: Mar 30, 2022 at 03:23 PM
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
  `recomm_start` int(255) NOT NULL,
  PRIMARY KEY (`deploymentID`),
  UNIQUE KEY `empathid_UNIQUE` (`deploymentID`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

--
-- Dumping data for table `recomm_saved_memory`
--

INSERT INTO `recomm_saved_memory` (`FirstStartDate`, `deploymentID`, `baselineTimeLeft`, `lastUpdated`, `morningStartTime`, `eveningEndTime`, `maxMessages`, `recomm_start`) VALUES
('2022-01-11 13:38:00', '54321', '0', '2022-03-30 09:17:10', '6:00:00', '23:00:00', 4, 1);

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
